/*
 * zeva_Bmsv3.c - V3 protocol differs from earlier versions supported in zeva_bms.c
 *
 * 08feb21,rgj added ZEVA_V3_FORCE_VOLTAGE_TEST
 * 17Oct20,rgj added per module active tracking, clear stale data if module stops responding (15s timeout to start)
 * 15may19,rgj removed MSG_OBJ_TX_INT_ENABLE flag from all tx buffers since dont need interrupt at end of tx
 * 26jan19,rgj Added timeouts to calc active modules, power off so bms inactive
 * 03jun18,rgj created from zeva_bms.c
 *   switched to irq call back as get overruns on polling callback due to v3 sending 4 messages in quick succession
 */


#if 0
V3 protocol vs V2
CanIDs start at 300 vs 100 (decimal)
Req now has 2 bytes vs 0, with shunt voltage parameter
resp packets different as now provide mV readings vs 100th before so packing different
No status messages any more
Sends 3 voltage + 1 temp so 4 messages very quickly (~1ms gaps) so could be lost
 use multiple CAN objs to handle the burst

  Determining active/not, number of modules reporting
When get voltage packet, update timestamp for that module and make bms active
periodically, calc how many modules from active time stamps, if none, bms inactive
#endif

#include "build_config.h"


#if defined(BMS) && defined (CANBUS) && defined (ZEVA_BMS)  && defined (ZEVA_BMS_V3)

#if 0 // define this in project config so code portable between projects
#define ZEVA_V3_UNIT_TEST
#define ZEVA_V3_FORCE_VOLTAGE_TEST // runs normally, but forces all cell voltages to debugger accessible value in data structure
#endif

#ifdef ZEVA_V3_FORCE_VOLTAGE_TEST
#warning ZEVA_V3_FORCE_VOLTAGE_TEST enabled
#endif


#include <xdc/runtime/log.h>


#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include <_lock.h>	// for _nop()

//#include "configuration.h"
#include "bms.h"

#include "zeva_bms.h"

#include "platform.h"
#include "can_driver.h"
#include "board.h"
#include "pack.h"

#define FAST_CALLBACK_MS 50 // 50ms - poll for data
#define SLOW_CALLBACK_MS 333 // 3 times a sec - check for timeouts = missing modules, bms inactive (perhaps powered off)

ZevaBMSInfoStruct ZevaBMSInfo;


struct {
    bool pause; // stop sending CAN msgs when set (by debugger)
	unsigned sequence; // controls which CAN message to send in call back
    unsigned vm;    // current module for voltage requests, used in call back
#ifdef ZEVA_DECODE_STATUS_CONFIG
    unsigned om;    // current module for other requests (status, config), used in call back
#endif
    unsigned otherCanId;  // could mean our rx mask capturing other devices
    unsigned badCanId; // not out of range but not decoded either - should never happen, zeva protocol change?
    unsigned rx1,rx2,rx3,rx4; // these counts should be same else indicates dropped packets
    unsigned balanceV;  // balancing on if set, off if zero
} zeva;


// VCU CAN transmit messages

// uses one CAN tx message object, sends different requests periodically
static uint8_t CANMsgTxZeva[2] = {0, 0};  // Shunt voltage (BE) 0 disables
static tCANMsgObject CANObjTxZeva = {300, 0, /* MSG_OBJ_TX_INT_ENABLE */0, 2, (uint8_t*)&CANMsgTxZeva}; // CANid changed at run time

// VCU CAN receive messages

// For example, module ID 0 will send packet IDs 301,302,303,304 in rapid succession (1ms gap)
// module ID 1 will use packet IDs 311 to 314, and so on
// range of Zeva responses 300 to 300 + 10*ZEVA_NUM_MODULES  Hex: 0x12c to 0x1a4 for 10 modules (120 cells)
// Would be better if Zeva used hex baseID more conducive to binary masking
#define CAN_RX_MASK 0xffffffff // must match every bit

// below CanID updated for each request to ensure capture xx1 xx2 xx3 xx4 xx5 messages in separate objs so none are lost
uint8_t CANMsgRxZevaBMS[4][8];
tCANMsgObject CANObjRxZevaBMS[4]; // contents initialized at run time


// One send at a time
static void sendZevaCanMsg(uint32_t canId)
{
	CANObjTxZeva.ui32MsgID = canId;
	CanTxMessage(Config.ZevaBMSCanChannel, ZEVA_BMS_CANTXOBJ1, &CANObjTxZeva);
}

// o is 0,4 or 8, m=module is 0,1,2-15
static void decodeV(int o, int m, tCANMsgObject *psCANMsg) {
	int i;
	uint16_t v;

    ZevaBMSInfo.module[m].tsLastUpdate = timeStamp64();
    ZevaBMSInfo.module[m].active = true;

    // FIXME improve this code, Bms.active should only be set if all modules are reporting
    Bms.tsLastUpdate = ZevaBMSInfo.module[m].tsLastUpdate;
    Bms.active = true; // well, at least one module reported

#ifdef PACK_STRINGS
    if (m < NUM_STRINGS)
        Pack.packMan.string[m].bmsActive = true;
#endif
	for (i = 0; i < 4; i++)
	{
		v =	(psCANMsg->pui8MsgData[i*2]<<8) + psCANMsg->pui8MsgData[i*2 + 1];
		ZevaBMSInfo.module[m].CellVoltage[o+i] = v; // write shared structure atomically
		if (!Bms.pause) {
#ifdef ZEVA_V3_FORCE_VOLTAGE_TEST
            if (ZevaBMSInfo.module[m].forceCellValue != 0) {
                v = ZevaBMSInfo.module[m].forceCellValue;
            }
#endif
		    Bms.CellVoltage[BmsFindCell(m,o+i)] = v / 10; // update generic bms data
		}
	}
}

static void decodeT(int m, tCANMsgObject *psCANMsg) {
    // zero data means temp sensor not present so save as zero, not -40
    ZevaBMSInfo.module[m].CellTemp[0] = (psCANMsg->pui8MsgData[0] == 0) ? 0 : psCANMsg->pui8MsgData[0]-40;
    ZevaBMSInfo.module[m].CellTemp[1] = (psCANMsg->pui8MsgData[1] == 0) ? 0 : psCANMsg->pui8MsgData[1]-40;

    // update generic bms data
    if (!Bms.pause) {
        Bms.CellTemp[BmsFindCell(m,0)] = ZevaBMSInfo.module[m].CellTemp[0] * 10;
        Bms.CellTemp[BmsFindCell(m,1)] = ZevaBMSInfo.module[m].CellTemp[1] * 10;
    }
}



// called from CAN driver when ever a response is received
static void decode(tCANMsgObject *psCANMsg) {
	int m;
	uint32_t canId = psCANMsg->ui32MsgID;


	if (canId<300 || canId>(300+(10*ZEVA_NUM_MODULES))) {
	    zeva.otherCanId = canId;
	    return; // Out of range
	}

#if 0 // this has been fixed
	/*
	 * FIXME - active ideally should not be set until there is valid data and bms has set max/min etc
	 *    possible startup race conditions with others reading the active state
	 */
    Bms.tsLastUpdate = timeStamp64();
    Bms.active = true;
    Bms.NumberOfModulesReporting = 1; // FIXME, really count these, timeout
#endif

    // FIXME this could be more efficient or at least constant time

	for (m=0; m < ZEVA_NUM_MODULES; m++)
	{
		if (canId == 301 + m*10)    // 1 = voltages 1-4
		{
		    zeva.rx1++;
			decodeV(0, m, psCANMsg);
			return;
		}
        if (canId == 302 + m*10)    // 2 = voltages 5-7
        {
            zeva.rx2++;
            decodeV(4, m, psCANMsg);
            return;
        }
        if (canId == 303 + m*10)    // 3 = voltages 8-12
        {
            zeva.rx3++;
            decodeV(8, m, psCANMsg);
            return;
        }
        if (canId == 304 + m*10)    // 4 = temps 1 & 2
        {
            zeva.rx4++;
            decodeT(m, psCANMsg);
            return;
        }
	}
    zeva.badCanId = canId;

}


// call every 50ms, or better,
static void fastCallBack(uint32_t milliseconds)
{
    int i;

    if (zeva.pause)
        return; // debugger use

    // prepare 4 rx objects for the burst of 5 messages the v3 module will send after the request
    for (i=0; i<4; i++)
    {
        CANObjRxZevaBMS[i].ui32MsgID = 301 + i + (10 * zeva.vm);
        // below to set with new mask each time
        CanRxMsgSetRegisterCallBack(Config.ZevaBMSCanChannel, ZEVA_BMS_CANRXOBJ+i, &CANObjRxZevaBMS[i], decode);
    }

	// sends one CAN request message every call
	//  so for 10 modules, 2*10*50ms = 500ms for each item to be updated
    sendZevaCanMsg(300 + (10 * zeva.vm)); // voltage1 request
//    if (++zeva.vm >= ZEVA_NUM_MODULES) zeva.vm = 0; // FIXME switch ZEVA_NUM_MODULES for Config.ExpectedBMSModules?
    if (++zeva.vm >= ZEVA_NUM_MODULES) zeva.vm = 0;

	zeva.sequence++;
}


// call 2 or 3 times a sec
// Use timeouts to detect inactive modules, or if none, make bms inactive
static void slowCallBack(uint32_t milliseconds)
{
#ifndef RGJTEST // disable this checking to skip when testing with no BMS
    int i, numModules;
// 1s    uint64_t overdue = timeStamp64() - MicrosecondsToClocks(1000000);
    uint64_t overdue;

    if (zeva.pause)
        return; // debugger use

    overdue = timeStamp64() - MicrosecondsToClocks(15 * 1e6); // 15s


    for (i = 0, numModules = 0; i < ZEVA_NUM_MODULES; i++)
    {
        if (ZevaBMSInfo.module[i].tsLastUpdate > overdue)
            numModules++;
        else {
#ifdef ZEVA_V3_FORCE_VOLTAGE_TEST
            if (ZevaBMSInfo.module[i].forceCellValue != 0) {
                numModules++;
                ZevaBMSInfo.module[i].active = true;
                if (i < NUM_STRINGS) {
                    int x;
                    Pack.packMan.string[i].bmsActive = true;
                    // zero out stale data for this module
                    for (x=0; x < ZEVA_CELLS_PER_MODULE; x++) {
                        ZevaBMSInfo.module[i].CellVoltage[x] = ZevaBMSInfo.module[i].forceCellValue;
                        Bms.CellVoltage[BmsFindCell(i,x)] = ZevaBMSInfo.module[i].forceCellValue / 10;
                    }
                    // reset temps also
                    ZevaBMSInfo.module[i].CellTemp[0] = 0;
                    ZevaBMSInfo.module[i].CellTemp[1] = 0;
                    Bms.CellTemp[BmsFindCell(i,0)] = 0;
                    Bms.CellTemp[BmsFindCell(i,1)] = 0;
                }
            } else {
#endif
            ZevaBMSInfo.module[i].active = false;
#ifdef PACK_STRINGS
            if (i < NUM_STRINGS) {
                int x;
                Pack.packMan.string[i].bmsActive = false;
                // zero out stale data for this module
                for (x=0; x < ZEVA_CELLS_PER_MODULE; x++) {
                    ZevaBMSInfo.module[i].CellVoltage[x] = 1; // use 1 rather than zero to distinguish on display stale data
                    Bms.CellVoltage[BmsFindCell(i,x)] = 1;
                }
                // reset temps also
                ZevaBMSInfo.module[i].CellTemp[0] = 0;
                ZevaBMSInfo.module[i].CellTemp[1] = 0;
                Bms.CellTemp[BmsFindCell(i,0)] = 0;
                Bms.CellTemp[BmsFindCell(i,1)] = 0;
            }
#endif // PACK_STRINGS
#ifdef ZEVA_V3_FORCE_VOLTAGE_TEST
            } // else above
#endif
        }
    }
    if (
           ((Bms.NumberOfModulesReporting = numModules) == 0)
        && (Bms.pause == false)  // this to allow debugger override
        ) {
        Bms.active = false;
        }
#endif
}

#ifdef UNIT_TEST // RGJ Test -pre fill with test data
static void unitTestInit()
{
    int m, c;

    for (m=0; m<ZEVA_NUM_MODULES; m++)
    {
        for (c=0;c<ZEVA_CELLS_PER_MODULE;c++)
        {
ZevaBMSInfo.module[m].CellVoltage[c] = m*100 + c;
            if (c < ZEVA_TEMPS_PER_MODULE)
                ZevaBMSInfo.module[m].CellTemp[c] = m*100 + c;
        }
    }
}
#endif // UNIT_TEST

void ZevaSetShuntVoltage(
        unsigned v) // V * 100 so 345 = 3.45V
{
    uint16_t be;
    unsigned vv = v * 10; // Zeva uses V*1000

    zeva.balanceV = v;

    // setup so mem write is big endian
    be = (vv << 8) & 0xff00;
    be |= (vv >> 8) & 0xff;

    // monotonic write to memory removes need for interrupt lock
    *(uint16_t *)&CANMsgTxZeva[0] = be;
}

void InitZevaBMS()
{
	Log_info0("InitZevaBMS");
#if 0 // zero at reset, not looking to restart at runtime, save some code space
	memset((void*)&ZevaBMSInfo, 0, sizeof(ZevaBMSInfo));
	memset((void*)&zeva, 0, sizeof(zeva));
#endif

	// init the 5 rx objects
	{
	    int i;
	    for (i=0; i<4; i++)
	    {
            CANObjRxZevaBMS[i].ui32MsgID
                = 301+i; // this overridden at run time so not really needed here
            CANObjRxZevaBMS[i].ui32MsgIDMask
                = 0xffffffff; // exact CanID match for this object
            CANObjRxZevaBMS[i].ui32Flags
                = MSG_OBJ_RX_INT_ENABLE | MSG_OBJ_USE_ID_FILTER;
            CANObjRxZevaBMS[i].ui32MsgLen
                = 8;
            CANObjRxZevaBMS[i].pui8MsgData
                = &CANMsgRxZevaBMS[i][0];
	        }
	}

	// No need to use IRQ callback since CAN objs will capture the fast can messages without dropping packets and next request much slower than timer call back rx processing

#ifdef UNIT_TEST // RGJ Test -pre fill with test data
	unitTestInit();
#endif

    mainRegister10msTimerIrqCallBack(FAST_CALLBACK_MS, fastCallBack);
    mainRegister10msTimerIrqCallBack(SLOW_CALLBACK_MS, slowCallBack);
    _nop();
}


#endif // defined(BMS) && defined (CANBUS) && defined (ZEVA_BMS_V3)
