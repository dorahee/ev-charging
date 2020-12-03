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

# scheduling-related parameters
exiting_load = True
if exiting_load:
    model_file = "scenario2-existing.mzn"
else:
    model_file = "scenario2.mzn"

# time-related parameters
start_time_day = "9:00"
end_time_day = "16:30"
num_periods_day = len(pd.date_range(start=start_time_day, end=end_time_day, freq='30Min'))
peak_periods = {14, 15}
off_peak_periods = {i for i in range(14)}

# EV-related parameters
num_evs = 10
max_charge = 25  # kW
total_energy = 20  # kWh

# tariffs or prices-related parameters
network_tariffs_peak = [0, 15, 15]
network_tariffs_off_peak = [0, 15, 3]


def read_data(file_prices_data="data/wholesale_data.csv", file_load_data="data/load_data.csv"):
    # read wholesale prices
    df_prices = pd.read_csv(rf"{file_prices_data}", index_col=0, parse_dates=True)
    df_prices_filtered = df_prices.between_time(start_time_day, end_time_day)
    df_datetimes_year = df_prices_filtered.index.to_frame()
    prices_year = df_prices_filtered.groupby(pd.Grouper(freq="M"))["WholesalePrice"].apply(list)

    # read existing loads
    df_loads = pd.read_csv(rf"{file_load_data}", index_col=0, parse_dates=True)
    df_loads_filtered = df_loads.between_time(start_time_day, end_time_day)
    loads_year = df_loads_filtered.groupby(pd.Grouper(freq="M"))["E"].apply(list)

    # read date time ranges
    months_year = prices_year.index
    datetimes_year = df_datetimes_year.groupby(pd.Grouper(freq="M"))["Datetime"].apply(list)

    return prices_year, loads_year, months_year, datetimes_year


def schedule_evs(num_days, prices_2d, loads_2d, network_tariff_peak, network_tariff_off_peak):

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
    ins["network_tariff_peak"] = network_tariff_peak
    ins["network_tariff_off_peak"] = network_tariff_off_peak
    ins["existing_loads"] = loads_2d
    result = ins.solve()

    return result


def transform_results(charge_ev_day_period, loads_month, prices_month, max_demand_peak, max_demand_off_peak):
    # combine results
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
        "Max_demand": [max_demand_peak if i%14 == 0 or i%15 == 0 else max_demand_off_peak for i in range(total_periods)]
    }
    bokeh_data_source = ColumnDataSource(combine_data_source)

    return combine_data_source, bokeh_data_source


def draw_monthly_graph(month, datetime_month, network_tariff_peak, network_tariff_off_peak, combine_data_source, bokeh_data_source,
                       prices_month, minizinc_outputs):
    WOD_dict = {}
    for i, s in enumerate([str(x) for x in datetime_month]):
        WOD_dict[i] = f"{s} {days_week[datetime.fromisoformat(s).weekday()]}"

    # draw graphs
    p_month = figure(title=f"{month}: network tariff = {network_tariff_peak} $/kW", plot_width=2000)
    p_month.yaxis.axis_label = "Demand (kW)"
    p_month.xaxis.formatter = FuncTickFormatter(code="""
                var labels = %s;
                return labels[tick];
            """ % WOD_dict)

    colour_index = -1
    legend_items = []
    for k, v in combine_data_source.items():
        if "Per" not in k:
            colour_index += 1
            if "Pri" not in k:
                pl = p_month.line(y=k, x='Periods',
                                  source=bokeh_data_source, line_width=2,
                                  color=colour_choices[colour_index])

            else:
                p_month.extra_y_ranges = {"WholesalePrices": Range1d(start=min(prices_month), end=max(prices_month))}
                p_month.add_layout(LinearAxis(y_range_name="WholesalePrices", axis_label="Price ($/kWh)"), 'right')
                pl = p_month.line(y=k, x='Periods',
                                  source=bokeh_data_source, line_width=2, line_dash="dashed",
                                  y_range_name='WholesalePrices', color=colour_choices[colour_index])
            legend_items.append((k, [pl]))

    legend = Legend(items=legend_items, location="center", orientation="horizontal", click_policy="hide")
    p_month.add_layout(legend, 'above')

    # make a data table
    datatable_source = ColumnDataSource(data=minizinc_outputs)
    columns = [TableColumn(field=k, title=k.replace("_", " "), formatter=NumberFormatter(format='0.00'))
               for k in minizinc_outputs.keys()]
    data_table = DataTable(source=datatable_source, columns=columns, width=2000, height=50)

    return p_month, data_table


def main():
    prices_year, loads_year, months_year, datetimes_year = read_data()

    # start scheduling
    tab_year = []
    minizinc_outputs_year = dict()
    for month, datetime_month, prices_month, loads_month in zip(months_year, datetimes_year, prices_year, loads_year):
        month = month.strftime("%Y-%m")

        # prepare input parameters
        num_days = int(len(prices_month) / num_periods_day)
        prices_2d = [list(x) for x in np.reshape(prices_month, (num_days, num_periods_day))]
        if exiting_load:
            loads_2d = [list(x) for x in np.reshape(loads_month, (num_days, num_periods_day))]
        else:
            loads_2d = [[0 for _ in range(num_periods_day)] for _ in range(num_days)]

        layout_month = []
        for network_tariff_peak, network_tariff_off_peak in zip(network_tariffs_peak, network_tariffs_off_peak):
            # start scheduling
            result = schedule_evs(num_days, prices_2d, loads_2d, network_tariff_peak, network_tariff_off_peak)

            # organise results
            charge_ev_day_period = result.solution.charge_strategy
            minizinc_outputs = ast.literal_eval(result.solution._output_item)
            minizinc_outputs_year["Result"] = list(minizinc_outputs.keys())
            minizinc_outputs_year[month] = [x[0] for x in list(minizinc_outputs.values())]
            max_demand_peak = minizinc_outputs["max_demand_peak"]
            max_demand_off_peak = minizinc_outputs["max_demand_off_peak"]
            print(f"{month} scheduled.")

            # transform and combine results
            combine_data_source, bokeh_data_source \
                = transform_results(charge_ev_day_period, loads_month, prices_month,
                                    max_demand_peak, max_demand_off_peak)

            # draw the monthly charge profile, the existing demand profile, the total demand profile and the prices
            p_month, data_table \
                = draw_monthly_graph(month, datetime_month, max_demand_peak, max_demand_off_peak,
                                     combine_data_source, bokeh_data_source, prices_month, minizinc_outputs)
            layout_month.extend([data_table, p_month])
        tab = Panel(child=layout(layout_month), title=month)
        tab_year.append(tab)

    # save plots
    print("Saving plots...")
    # df = pd.DataFrame.from_dict(minizinc_outputs_year).transpose()
    # df.columns = df.iloc[0]
    # df = df[1:]
    # minizinc_outputs_year_source = ColumnDataSource(data=df)
    # data_table = DataTable(source=minizinc_outputs_year_source, width=2000, height=500)
    # tab = Panel(child=data_table, title="Yearly Costs and Maximum Demands")
    # tab_year.insert(0, tab)

    output_file(f"demands_year.html")
    output_graph = layout(row(Tabs(tabs=tab_year)), sizing_mode="scale_width")
    save(output_graph)
    show(output_graph)
    print("Done.")


if __name__ == '__main__':
    main()
