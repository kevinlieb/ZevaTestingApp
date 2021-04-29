/*
 * zeva_bms.h
 *
 * 03jun18,rgj Support for V3, ZEVA_DECODE_STATUS_CONFIG defined in v2 driver, not used in v3
 *              voltage scale now mV, v2 driver updated tho physically on supports 100ths
 * 20Feb18,rgj Added status and config decoding
 * 19feb18,rgj removed active to generic bms
 * 02feb18,bjw added ZevaIsActive
 * 20aug17,rgj Renamed ZEVA_MAX_MODULES. ZEVA_TEMPS_PER_MODULE, ZEVA_CELLS_PER_MODULE no effective change
 * 25may17,rgj removed callback, now self registers
 * 09may17,rgj refactor pack & variable naming conventions
 * 05May17,rgj updated
 * 25Apr17,bbw created
 */

#ifndef ZEVA_BMS_H
#define ZEVA_BMS_H

#include <stdbool.h>
#include <stdint.h>

#include "driverlib/can.h"
#include "configuration.h"

#ifndef ZEVA_NUM_MODULES
#define ZEVA_NUM_MODULES 	 10 // Zeva supports up to 12/16 modules, watch ram consumption
#endif
#define ZEVA_CELLS_PER_MODULE 12
#define ZEVA_TEMPS_PER_MODULE 2

typedef struct
{
    bool    active;     // set when rx update, cleared after timeout
    uint64_t tsLastUpdate;   // timestamp of last update
	uint16_t CellVoltage[ZEVA_CELLS_PER_MODULE]; // scale: /1000 V3  /100 V2
	int16_t  CellTemp[ZEVA_TEMPS_PER_MODULE]; // scale C*1 signed converted from C+40 from device
#ifdef ZEVA_DECODE_STATUS_CONFIG // Only relevant for v2 HW
    uint8_t  status[5];
    uint8_t  config[8];
#endif
#ifdef ZEVA_V3_FORCE_VOLTAGE_TEST
    uint16_t forceCellValue; // debug/testing use.  if non zero, cell voltages forced to this value
#endif
} ZevaBMSModuleInfoStruct;

typedef struct
{
	ZevaBMSModuleInfoStruct module[ZEVA_NUM_MODULES];
} ZevaBMSInfoStruct;

extern ZevaBMSInfoStruct ZevaBMSInfo;

void ZevaSetShuntVoltage(
        unsigned v); // V * 100 so 345 = 3.45V

void InitZevaBMS();


#endif /* ZEVA_BMS_H */
