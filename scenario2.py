import pandas as pd
import seaborn as sns
import minizinc as mzn
import numpy as np
import ast
from pandas_bokeh import *
from bokeh.layouts import layout
from bokeh.models import *
from bokeh.plotting import figure, output_file
from bokeh.palettes import Set2
from datetime import datetime
from math import pi

colour_choices = Set2[8]
days_week = {
    0: "Mon.",
    1: "Tue.",
    2: "Wed.",
    3: "Thurs.",
    4: "Fri.",
    5: "Sat.",
    6: "Sun"
}

exiting_load = True
if exiting_load:
    model_file = "scenario2-existing.mzn"
else:
    model_file = "scenario2.mzn"

# parameters

start_time_day = "9:00"
end_time_day = "16:30"
num_periods_day = len(pd.date_range(start=start_time_day, end=end_time_day, freq='30Min'))

num_evs = 10
max_charge = 25  # kW
total_energy = 20  # kWh
network_tariff = 15

# read wholesale prices
df_prices = pd.read_csv(r"data/wholesale_data.csv", index_col=0, parse_dates=True)
df_prices_filtered = df_prices.between_time(start_time_day, end_time_day)
df_datetimes_year = df_prices_filtered.index.to_frame()
prices_year = df_prices_filtered.groupby(pd.Grouper(freq="M"))["WholesalePrice"].apply(list)

# read existing loads
df_loads = pd.read_csv(r"data/load_data.csv", index_col=0, parse_dates=True)
df_loads_filtered = df_loads.between_time(start_time_day, end_time_day)
loads_year = df_loads_filtered.groupby(pd.Grouper(freq="M"))["E"].apply(list)

# read date time ranges
months_year = prices_year.index
datetimes_year = df_datetimes_year.groupby(pd.Grouper(freq="M"))["Datetime"].apply(list)

# start scheduling
df_charge_strategies = pd.DataFrame()
tab_year = []
for month, datetime_month, prices_month, loads_month in zip(months_year, datetimes_year, prices_year, loads_year):
    month = month.strftime("%Y-%m")
    num_days = int(len(prices_month) / num_periods_day)
    prices_2d = [list(x) for x in np.reshape(prices_month, (num_days, num_periods_day))]

    # build a MiniZinc model
    model = mzn.Model(model_file)
    solver = mzn.Solver.lookup("coin-bc")
    ins = mzn.Instance(solver, model)
    ins["num_days"] = num_days
    ins["num_periods_day"] = num_periods_day
    ins["num_evs"] = num_evs
    ins["max_charge"] = max_charge
    ins["total_energy"] = total_energy
    ins["wholesale_prices"] = prices_2d
    ins["network_tariff"] = network_tariff
    if exiting_load:
        loads_2d = [list(x) for x in np.reshape(loads_month, (num_days, num_periods_day))]
    else:
        loads_2d = [[0 for _ in range(num_periods_day)] for _ in range(num_days)]
    ins["existing_loads"] = loads_2d

    result = ins.solve()
    charge_ev_day_period = result.solution.charge_strategy
    minizinc_outputs = ast.literal_eval(result.solution._output_item)
    wholesale_cost = minizinc_outputs["wholesale_cost"]
    network_charge = minizinc_outputs["network_charge"]
    max_demand = minizinc_outputs["max_demand"]
    print(f"{month} scheduled.")

    # process results
    charge_month = []
    for charge_ev in charge_ev_day_period:
        charge_ev_month = []
        for charge_ev_day in charge_ev:
            charge_ev_month.extend(charge_ev_day)
        charge_month.append(charge_ev_month)
    total_charge_month = np.sum(charge_month, axis=0).tolist()
    demand_month = [x * 0.5 for x in loads_month]
    total_demand_month = [c + l for c, l in zip(total_charge_month, demand_month)]
    total_periods = len(loads_month)
    combine_data_source = {
        # "Periods": [x.strftime("%Y-%m-%H-%M-%S") for x in datetime_month],
        "Periods": [i for i in range(total_periods)],
        "EVs": total_charge_month,
        "Existing": demand_month,
        "Total": total_demand_month,
        "Prices": prices_month,
        "Max_demand": [max_demand for _ in range(total_periods)]
    }
    bokeh_data_source = ColumnDataSource(combine_data_source)

    p_month = figure(title=f"EVs vs Existing vs Total of {month}", plot_width=2000)
    p_month.yaxis.axis_label = "Demand (kW)"
    # p_month.xaxis.ticker = [i for i in range(total_periods) if i % num_periods_day == 0]
    # p_month.xaxis.major_label_orientation = pi/4

    label_dict = {}
    for i, s in enumerate([str(x) for x in datetime_month]):
        label_dict[i] = f"{s} {days_week[datetime.fromisoformat(s).weekday()]}"
    p_month.xaxis.formatter = FuncTickFormatter(code="""
        var labels = %s;
        return labels[tick];
    """ % label_dict)

    colour_index = -1
    legend_items = []
    for k, v in combine_data_source.items():
        if "Per" not in k:
            colour_index += 1
            plot = None
            if "Pri" not in k:
                plot = p_month.line(y=k, x='Periods',
                                    source=bokeh_data_source, line_width=2,
                                    color=colour_choices[colour_index])

            else:
                p_month.extra_y_ranges = {"WholesalePrices": Range1d(start=min(prices_month), end=max(prices_month))}
                p_month.add_layout(LinearAxis(y_range_name="WholesalePrices", axis_label="Price ($/kWh)"), 'right')
                plot = p_month.line(y=k, x='Periods',
                                    source=bokeh_data_source, line_width=2, line_dash="dashed",
                                    y_range_name='WholesalePrices', color=colour_choices[colour_index])
            legend_items.append((k, [plot]))
            # tooltips = [
            #     # ('Periods', '$EVs'),
            #     (k, f'${k}')
            # ]
            # p_month.tools.append(HoverTool(mode="vline", renderers=[plot]))

    legend = Legend(items=legend_items, location="center", orientation="horizontal", click_policy="hide")
    p_month.add_layout(legend, 'above')

    datatable_source = ColumnDataSource(data=minizinc_outputs)
    columns = [TableColumn(field=k, title=k.replace("_", " "), formatter=NumberFormatter(format='0.00'))
               for k in minizinc_outputs.keys()]

    data_table = DataTable(source=datatable_source, columns=columns, width=2000, height=50)

    tab = Panel(child=layout(column(data_table, p_month)), title=month)
    tab_year.append(tab)

print("Saving plots...")
output_file(f"demands_year.html")
output_graph = layout(row(Tabs(tabs=tab_year)), sizing_mode="scale_width")
save(output_graph)
show(output_graph)
print("Done.")
