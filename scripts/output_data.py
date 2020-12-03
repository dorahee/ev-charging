from pandas_bokeh import *
from bokeh.layouts import layout
from bokeh.models import *
from bokeh.plotting import figure, output_file
from bokeh.palettes import Set2
from datetime import datetime
import numpy as np

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


def merge_results(num_days, charge_ev_day_period, loads_month, prices_month, datetime_month,
                  max_demand_peak, max_demand_off_peak,
                  peak_periods, off_peak_periods, network_tariff_peak, network_tariff_off_peak):
    # combine results
    charge_month = []
    for charge_ev in charge_ev_day_period:
        charge_ev_month = []
        for charge_ev_day in charge_ev:
            charge_ev_month.extend(charge_ev_day)
        charge_month.append(charge_ev_month)
    total_charge_month = np.sum(charge_month, axis=0).tolist()
    demand_month = [x * 2 for x in loads_month]
    total_demand_month = [c + l for c, l in zip(total_charge_month, demand_month)]
    total_periods = len(loads_month)
    peak_periods_month = [v for i, v in enumerate(range(total_periods))
                          if 16 <= datetime_month[i].hour <= 21]
    wholesale_cost_month = [x * y * 0.001 * 0.5 for x, y in zip(total_demand_month, prices_month)]

    combine_data_source_dict = {
        "Datetime": [timestamp.strftime("%Y-%m-%d %H:%M:%S") for timestamp in datetime_month],
        "Periods": [i for i in range(total_periods)],
        "EVs": total_charge_month,
        "Existing": demand_month,
        "Total": total_demand_month,
        "Prices": prices_month,
        "Max": [max_demand_peak[0] if i in peak_periods_month else max_demand_off_peak[0] for i in
                       range(total_periods)],
        "WCost": wholesale_cost_month,
        # "NCharge": network_charge_month,
        # "Obj": [x + y for x, y in zip(wholesale_cost_month, network_charge_month)],
    }
    return combine_data_source_dict


def visualise_monthly_results(figure_title, month, datetime_month, network_tariff_peak, network_tariff_off_peak,
                              data_source_dict, prices_month, minizinc_outputs):
    bokeh_data_source = ColumnDataSource(data_source_dict)
    WOD_dict = {}
    for i, s in enumerate([str(x) for x in datetime_month]):
        WOD_dict[i] = f"{s} {days_week[datetime.fromisoformat(s).weekday()]}"

    # draw graphs
    p_month = figure(title=figure_title, plot_width=2000, plot_height=500)
    p_month.yaxis.axis_label = "Demand (kW)"
    p_month.xaxis.formatter = FuncTickFormatter(code="""
                var labels = %s;
                return labels[tick];
            """ % WOD_dict)

    colour_index = -1
    legend_items = []
    tooltips = []
    tooltips.append((f'Datetime', f"@Datetime"))
    for k, v in data_source_dict.items():
        legend_label = None
        if "Per" not in k and "Cost" not in k and "Obj" not in k and "Char" not in k and "Date" not in k:
            colour_index += 1
            if "Pri" not in k:
                pl = p_month.line(y=k, x='Periods',
                                  source=bokeh_data_source, line_width=2,
                                  color=colour_choices[colour_index])
                tooltips.append((f'{k}', f"@{k} kW"))
                legend_label = f"Out: {k} demand"
                if "Ex" in k:
                    legend_label = f"In: {k} demand"

            else:
                p_month.extra_y_ranges = {"WholesalePrices": Range1d(start=min(prices_month), end=max(prices_month))}
                p_month.add_layout(LinearAxis(y_range_name="WholesalePrices", axis_label="Price ($/kWh)"), 'right')
                pl = p_month.line(y=k, x='Periods',
                                  source=bokeh_data_source, line_width=2, line_dash="dashed",
                                  y_range_name='WholesalePrices', color=colour_choices[colour_index])
                tooltips.append((f'{k}', f"@{k} $/MWh"))
                hover1 = HoverTool(renderers=[pl], tooltips=tooltips, point_policy='follow_mouse',
                                   mode='vline')
                p_month.add_tools(hover1)
                legend_label = f"In: {k}"

            if legend_label is None:
                legend_label = f"Out: {k} demand"
            legend_items.append((legend_label, [pl]))
        elif "Date" not in k and "Per" not in k:
            tooltips.append((f'{k}', f"@{k}"))

    legend = Legend(items=legend_items, location="center", orientation="horizontal", click_policy="hide")
    p_month.add_layout(legend, 'above')

    # make a data table
    datatable_source = ColumnDataSource(data=minizinc_outputs)
    columns = [TableColumn(field=k, title=k.replace("_", " "), formatter=NumberFormatter(format='0.00'))
               for k in minizinc_outputs.keys()]
    data_table = DataTable(source=datatable_source, columns=columns, width=2000, height=80)

    return p_month, data_table
