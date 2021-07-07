import plotly.express as px
import pandas as pd

df = pd.read_csv('voltages_20210706.csv')
df.head()

#print(df["v12"])

fig = px.line(df, x="time", y=["v1","v2","v3","v4","v5","v6","v7","v8","v9","v10","v11","v12","v13","v14","v15","v16","v17","v18","v19","v20","v21","v22","v23","v24","v25","v26","v27","v28","v29","v30","v31","v32","c"], render_mode='svg')
fig.show()
