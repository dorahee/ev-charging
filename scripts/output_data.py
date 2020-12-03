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
    for k, v in data_source_dict.items():
        legend_label = None
        if "Per" not in k and "Cost" not in k and "Obj" not in k and "Char" not in k:
            colour_index += 1
            if "Pri" not in k:
                pl = p_month.line(y=k, x='Periods',
                                  source=bokeh_data_source, line_width=2,
                                  color=colour_choices[colour_index])
                tooltips.append((f'{k}', f"@{k} kW"))
                legend_label = f"Out:{k}"
                if "Ex" in k:
                    legend_label = f"In:{k}"

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
                legend_label = f"In:{k}"

            if legend_label is None:
                legend_label = f"Out:{k}"
            legend_items.append((legend_label, [pl]))
        else:
            tooltips.append((f'{k}', f"@{k}"))

    legend = Legend(items=legend_items, location="center", orientation="horizontal", click_policy="hide")
    p_month.add_layout(legend, 'above')

    # make a data table
    datatable_source = ColumnDataSource(data=minizinc_outputs)
    columns = [TableColumn(field=k, title=k.replace("_", " "), formatter=NumberFormatter(format='0.00'))
               for k in minizinc_outputs.keys()]
    data_table = DataTable(source=datatable_source, columns=columns, width=2000, height=50)

    return p_month, data_table
