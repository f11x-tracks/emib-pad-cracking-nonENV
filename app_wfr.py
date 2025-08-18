


import pandas as pd
import dash
from dash import dcc, html
import plotly.express as px
import dash_table

# Read data
delay_df = pd.read_csv('data-wfr-lvl-delay-time.csv')
goodbad_df = pd.read_csv('data-wfr-lvl-good-bad.txt')

# Merge GVB from goodbad_df into delay_df using WAFER_ID
merged_gvb = goodbad_df[['WAFER_ID', 'GVB']]
delay_df = delay_df.merge(merged_gvb, on='WAFER_ID', how='left')

# Calculate DELAY_TIME for each WAFER_ID
def calculate_delay_time(df):
		results = []
		for wafer_id in df['WAFER_ID'].unique():
			wafer_data = df[df['WAFER_ID'] == wafer_id]
			# Find END_DATE for OPN=194997 and CHAMBER startswith 'CGCH'
			end_rows = wafer_data[(wafer_data['OPN'] == 194997) & (wafer_data['CHAMBER'].str.startswith('CGCH'))]
			# Find START_DATE for OPN=197573 and CHAMBER startswith 'PC'
			start_rows = wafer_data[(wafer_data['OPN'] == 197573) & (wafer_data['CHAMBER'].str.startswith('PC'))]
			if not end_rows.empty and not start_rows.empty:
				# Use the most recent END_DATE and START_DATE
				end_date = pd.to_datetime(end_rows['END_DATE']).max()
				start_date = pd.to_datetime(start_rows['START_DATE']).max()
				delay_time = (start_date - end_date).total_seconds() / 3600.0
				gvb = wafer_data.iloc[0]['GVB']
				results.append({'WAFER_ID': wafer_id, 'DELAY_TIME': delay_time, 'GVB': gvb})
		return pd.DataFrame(results)



plot_df = calculate_delay_time(delay_df)
plot_df = plot_df.dropna(subset=['GVB'])
print('First 20 rows of plot_df (GVB not null):')
print(plot_df.head(20))

# Dash app
app = dash.Dash(__name__)
app.layout = html.Div([
	html.H2('Wafer Delay Time vs GVB'),
	dcc.Graph(
		id='delay-gvb-scatter',
		figure=px.scatter(
			plot_df,
			x='DELAY_TIME',
			y='GVB',
			hover_data=['WAFER_ID'],
			title='DELAY_TIME (hrs) vs GVB'
		)
	),
	html.Hr(),
	html.H3('Wafer Delay Table'),
	dash_table.DataTable(
		id='wafer-delay-table',
		columns=[
			{'name': 'WAFER_ID', 'id': 'WAFER_ID'},
			{'name': 'DELAY_TIME', 'id': 'DELAY_TIME'}
		],
		data=plot_df[['WAFER_ID', 'DELAY_TIME']].to_dict('records'),
		page_size=10,
		style_table={'height': '300px', 'overflowY': 'auto'},
		style_cell={'textAlign': 'left'},
		style_header={'fontWeight': 'bold'},
		sort_action='native',
	)
])

if __name__ == '__main__':
	app.run_server(debug=True)

