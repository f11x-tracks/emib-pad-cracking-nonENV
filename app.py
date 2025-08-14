import pandas as pd
import dash
from dash import dcc, html
import plotly.express as px

# Read CSV
df = pd.read_csv('data.csv')

# --- Merge Lot-good-bad.csv columns ---
lot_good_bad = pd.read_csv('Lot-good-bad.csv')
df = df.merge(lot_good_bad, on='LOT', how='left')
df['Fab Defect Scans'] = df['Fab Defect Scans'].fillna('NA')  # <-- mark missing as 'NA'
df['Nrows'] = df['Nrows'].fillna('NA')
df['Nlot'] = df['Nlot'].fillna('NA')
df['DiePrep CIM'] = df['DiePrep CIM'].fillna('NA')

# Filter for OPN 194997 and 197573
def format_opn(opn):
    try:
        return str(int(float(opn)))
    except:
        return str(opn)
opn_desc_map = {}
for opn_val in df['OPN'].unique():
    if pd.notnull(opn_val):
        opn_str = format_opn(opn_val)
        desc = df[df['OPN'].apply(format_opn) == opn_str]['OPER_SHORT_DESC'].iloc[0] if 'OPER_SHORT_DESC' in df.columns else ''
        opn_desc_map[opn_str] = f"{opn_str} - {desc}" if desc else opn_str
unique_opns = sorted(opn_desc_map.keys())
opn_dfs = {opn: df[df['OPN'].apply(format_opn) == opn].copy() for opn in unique_opns}

# Calculate DELAY_TIME and add ENTITY for matching LOTs
def calculate_delay_time(start_opn, end_opn):
    df_start = opn_dfs[start_opn]
    df_end = opn_dfs[end_opn]
    delay_times = []
    entities = []
    multi_counts = []
    split_values = []
    for idx, row in df_start.iterrows():
        lot = row['LOT']
        lot_rows = df_end[df_end['LOT'] == lot]
        multi_count = len(lot_rows)
        if multi_count > 0:
            lot_rows = lot_rows.copy()
            lot_rows['LAST_WAFER_END_DATE'] = pd.to_datetime(lot_rows['LAST_WAFER_END_DATE'])
            most_recent_row = lot_rows.loc[lot_rows['LAST_WAFER_END_DATE'].idxmax()]
            end_start = pd.to_datetime(row['LAST_WAFER_END_DATE'])
            end_end = most_recent_row['LAST_WAFER_END_DATE']
            delay = round((end_end - end_start).total_seconds() / 3600, 1)
            entity = most_recent_row['ENTITY']
            qty_start = row['QTY']
            qty_end = most_recent_row['QTY']
            split = 'YES' if qty_start != qty_end else 'NO'
        else:
            delay = None
            entity = None
            split = 'NO'
        delay_times.append(delay)
        entities.append(entity)
        multi_counts.append(multi_count)
        split_values.append(split)
    df_result = df_start.copy()
    df_result['DELAY_TIME'] = delay_times
    df_result['ENTITY_END_OPN'] = entities
    df_result['MULTI'] = multi_counts
    df_result['SPLIT'] = split_values
    return df_result

# Chart: DELAY_TIME distribution
default_start_opn = unique_opns[0]
default_end_opn = unique_opns[1] if len(unique_opns) > 1 else unique_opns[0]
df_delay = calculate_delay_time(default_start_opn, default_end_opn)
df_delay_unique = df_delay.sort_values('LAST_WAFER_END_DATE').dropna(subset=['DELAY_TIME']).drop_duplicates(subset=['LOT'], keep='last')
min_date = pd.to_datetime(df_delay_unique['LAST_WAFER_END_DATE']).min().date()
max_date = pd.to_datetime(df_delay_unique['LAST_WAFER_END_DATE']).max().date()
fig = px.scatter(
    df_delay_unique,
    x='DELAY_TIME',
    y='ENTITY',
    color='Fab Defect Scans',
    color_discrete_map={'Clean': 'green', 'Defects': 'red'},  # custom color mapping
    title='DELAY_TIME vs ENTITY Scatter',
    hover_data=['LOT', 'MULTI', 'SPLIT', 'LOT_ABORT_FLAG', 'QTY', 'DOTPROCESS', 'PRODUCT', 'LAST_WAFER_END_DATE'] + [col for col in lot_good_bad.columns if col != 'LOT']
)
app = dash.Dash(__name__)

app.layout = html.Div([
    html.H1('DELAY_TIME Analysis'),
    dcc.DatePickerRange(
        id='date-picker-range',
        min_date_allowed=min_date,
        max_date_allowed=max_date,
        start_date=min_date,
        end_date=max_date
    ),
    html.Button('Reset Dates', id='reset-dates-btn', n_clicks=0),
    html.Div([
        html.Label('Start OPN:'),
        dcc.Dropdown(
            id='start-opn-dropdown',
            options=[{'label': opn_desc_map[opn], 'value': opn} for opn in unique_opns],
            value=default_start_opn,
            clearable=False,
            style={'width': '340px'}
        ),
        html.Label('End OPN:'),
        dcc.Dropdown(
            id='end-opn-dropdown',
            options=[{'label': opn_desc_map[opn], 'value': opn} for opn in unique_opns],
            value=default_end_opn,
            clearable=False,
            style={'width': '340px'}
        ),
        html.Label('ENTITY OPN:'),
        dcc.Dropdown(
            id='entity-opn-dropdown',
            options=[{'label': opn_desc_map[opn], 'value': opn} for opn in unique_opns],
            value=default_end_opn,
            clearable=False,
            style={'width': '340px'}
        ),
    ], style={'display': 'flex', 'gap': '20px', 'alignItems': 'center'}),
    dcc.Dropdown(
        id='lot-dropdown',
        options=[{'label': str(lot), 'value': lot} for lot in df_delay_unique['LOT'].unique()],
        placeholder='Select a LOT',
        multi=False
    ),
    dcc.Graph(id='scatter-plot', figure=fig),
    html.Button('Export to Excel', id='export-excel-btn', n_clicks=0),
    dcc.Download(id='download-dataframe-xlsx'),
    html.H2('Summary Statistics by ENTITY'),
    html.Div(id='summary-table'),
    html.H2('LOT Count by ENTITY and Month'),
    dcc.Graph(id='lot-entity-month-plot')
])

from dash.dependencies import Output, Input, State

@app.callback(
    [Output('date-picker-range', 'start_date'), Output('date-picker-range', 'end_date')],
    [Input('reset-dates-btn', 'n_clicks')],
    [State('date-picker-range', 'start_date'), State('date-picker-range', 'end_date')]
)
def reset_dates(n_clicks, start_date, end_date):
    if n_clicks:
        return min_date, max_date
    return start_date, end_date

@app.callback(
    Output('download-dataframe-xlsx', 'data'),
    Input('export-excel-btn', 'n_clicks'),
    State('lot-dropdown', 'value'),
    State('date-picker-range', 'start_date'),
    State('date-picker-range', 'end_date'),
    prevent_initial_call=True
)
def export_to_excel(n_clicks, selected_lot, start_date, end_date):
    if n_clicks:
        filtered_df = df_delay_unique.copy()
        if start_date and end_date:
            filtered_df = filtered_df[(pd.to_datetime(filtered_df['LAST_WAFER_END_DATE']).dt.date >= pd.to_datetime(start_date).date()) &
                                      (pd.to_datetime(filtered_df['LAST_WAFER_END_DATE']).dt.date <= pd.to_datetime(end_date).date())]
        if selected_lot:
            filtered_df = filtered_df[filtered_df['LOT'] == selected_lot]
        return dcc.send_data_frame(filtered_df.to_excel, 'filtered_data.xlsx', index=False)
    return None

@app.callback(
        [Output('scatter-plot', 'figure'), Output('summary-table', 'children'), Output('lot-entity-month-plot', 'figure'), Output('lot-dropdown', 'options')],
        [Input('start-opn-dropdown', 'value'),
         Input('end-opn-dropdown', 'value'),
         Input('entity-opn-dropdown', 'value'),
         Input('lot-dropdown', 'value'),
         Input('date-picker-range', 'start_date'),
         Input('date-picker-range', 'end_date')]
)
def update_figure(start_opn, end_opn, entity_opn, selected_lot, start_date, end_date):
    import numpy as np
    df_delay = calculate_delay_time(start_opn, end_opn)
    df_delay_unique = df_delay.sort_values('LAST_WAFER_END_DATE').dropna(subset=['DELAY_TIME']).drop_duplicates(subset=['LOT'], keep='last')
    filtered_df = df_delay_unique.copy()
    # Use ENTITY values from selected ENTITY_OPN
    entity_df = opn_dfs[entity_opn]
    entity_map = dict(zip(entity_df['LOT'], entity_df['ENTITY']))
    filtered_df['ENTITY_FOR_PLOT'] = filtered_df['LOT'].map(entity_map)
    # Prepare Year-Month column
    filtered_df['YEAR_MONTH'] = pd.to_datetime(filtered_df['LAST_WAFER_END_DATE']).dt.to_period('M').astype(str)
    lot_month_counts = filtered_df.groupby(['YEAR_MONTH', 'ENTITY_FOR_PLOT'])['LOT'].count().reset_index().rename(columns={'ENTITY_FOR_PLOT': 'ENTITY'})
    month_plot = px.bar(
        lot_month_counts,
        x='YEAR_MONTH',
        y='LOT',
        color='ENTITY',
        barmode='group',
        title='LOT Count by ENTITY and Month',
        labels={'LOT': 'LOT Count', 'YEAR_MONTH': 'Year-Month'}
    )
    month_plot.update_xaxes(tickangle=90)
    # Filter by date range
    if start_date and end_date:
        filtered_df = filtered_df[(pd.to_datetime(filtered_df['LAST_WAFER_END_DATE']).dt.date >= pd.to_datetime(start_date).date()) &
                                  (pd.to_datetime(filtered_df['LAST_WAFER_END_DATE']).dt.date <= pd.to_datetime(end_date).date())]
    # Filter by LOT
    if selected_lot:
        filtered_df = filtered_df[filtered_df['LOT'] == selected_lot]
    lot_options = [{'label': str(lot), 'value': lot} for lot in filtered_df['LOT'].unique()]
    jitter_strength = 0.05
    if not filtered_df.empty:
        filtered_df['ENTITY_JITTER'] = filtered_df['ENTITY_FOR_PLOT']
        if np.issubdtype(filtered_df['ENTITY_FOR_PLOT'].dtype, np.number):
            filtered_df['ENTITY_JITTER'] += np.random.uniform(-jitter_strength, jitter_strength, size=len(filtered_df))
        else:
            entity_unique = [str(v) for v in filtered_df['ENTITY_FOR_PLOT'].unique()]
            entity_plot_map = {v: i for i, v in enumerate(sorted(entity_unique))}
            filtered_df['ENTITY_NUM'] = filtered_df['ENTITY_FOR_PLOT'].astype(str).map(entity_plot_map)
            filtered_df['ENTITY_JITTER'] = filtered_df['ENTITY_NUM'] + np.random.uniform(-jitter_strength, jitter_strength, size=len(filtered_df))
    fig = px.scatter(
        filtered_df,
        x='DELAY_TIME',
        y='ENTITY_JITTER',
        color='Fab Defect Scans',
        color_discrete_map={'Clean': 'green', 'Defects': 'red'},  # custom color mapping
        title='DELAY_TIME vs ENTITY Scatter (Y Jittered)',
        hover_data=['LOT', 'MULTI', 'SPLIT', 'LOT_ABORT_FLAG', 'QTY', 'DOTPROCESS', 'PRODUCT', 'LAST_WAFER_END_DATE', 'ENTITY_FOR_PLOT'] + [col for col in lot_good_bad.columns if col != 'LOT']
    )
    fig.update_xaxes(title_text='DELAY_TIME (hours)')
    if not filtered_df.empty and not np.issubdtype(filtered_df['ENTITY_FOR_PLOT'].dtype, np.number):
        entity_unique = [str(v) for v in filtered_df['ENTITY_FOR_PLOT'].unique()]
        entity_plot_map = {v: i for i, v in enumerate(sorted(entity_unique))}
        fig.update_yaxes(
            tickvals=list(entity_plot_map.values()),
            ticktext=list(entity_plot_map.keys()),
            title_text='ENTITY'
        )
    else:
        fig.update_yaxes(title_text='ENTITY')

    if not filtered_df.empty:
        summary = filtered_df.groupby('ENTITY').agg(
            count=('DELAY_TIME', 'count'),
            mean_delay=('DELAY_TIME', 'mean'),
            min_delay=('DELAY_TIME', 'min'),
            max_delay=('DELAY_TIME', 'max'),
            split_yes=('SPLIT', lambda x: (x == 'YES').sum())
        ).reset_index()
        table_header = [html.Tr([html.Th(col, style={'border': '1px solid black', 'padding': '4px'}) for col in summary.columns])]
        table_rows = []
        for _, row in summary.iterrows():
            cells = []
            for col in summary.columns:
                val = row[col]
                if col == 'mean_delay' and pd.notnull(val):
                    val = f"{val:.1f}"
                cells.append(html.Td(val, style={'border': '1px solid black', 'padding': '4px'}))
            table_rows.append(html.Tr(cells))
        summary_table = html.Table(table_header + table_rows, style={'width': '100%', 'borderCollapse': 'collapse', 'border': '1px solid black'})
    else:
        summary_table = html.Div('No data for selected filters.')
    return (fig, summary_table, month_plot, lot_options)

if __name__ == '__main__':
    app.run(debug=True)