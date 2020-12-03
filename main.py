import numpy as np
from pandas_bokeh import *
from bokeh.layouts import layout
from bokeh.models import *
from bokeh.plotting import figure, output_file
from bokeh.palettes import Set2
from datetime import datetime, date
import scripts.ev_scheduling as ev
import scripts.import_data as input
import scripts.output_data as output

this_date = str(date.today())
this_time = str(datetime.now().time().strftime("%H-%M-%S"))
this_date_time = f"{this_date}-{this_time}"

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
network_tariffs_peak = [0, 15, 15, 15, 0]
network_tariffs_off_peak = [0, 15, 3, 0, 15]
network_tariffs_peak = [15]
network_tariffs_off_peak = [3]


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
                          if datetime_month[i].hour >= 16 and datetime_month[i].hour <= 21]
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


def main(use_existing_load, use_wholesale_prices):
    # import input data
    prices_year, loads_year, months_year, datetimes_year = input.read_data(start_time_day, end_time_day, )

    # start scheduling
    tab_year = []
    minizinc_outputs_year = dict()
    for month, datetime_month, prices_month, loads_month in zip(months_year, datetimes_year, prices_year, loads_year):
        month = month.strftime("%Y-%m")

        # prepare input parameters
        num_days = int(len(prices_month) / num_periods_day)
        num_periods = len(prices_month)

        if use_wholesale_prices:
            prices_2d = [list(x) for x in np.reshape(prices_month, (num_days, num_periods_day))]
        else:
            prices_month = [0 for _ in range(num_periods)]
            prices_2d = [[0 for _ in range(num_periods_day)] for _ in range(num_days)]

        if use_existing_load:
            loads_2d = [list(x) for x in np.reshape(loads_month, (num_days, num_periods_day))]
        else:
            loads_month = [0 for _ in range(num_periods)]
            loads_2d = [[0 for _ in range(num_periods_day)] for _ in range(num_days)]

        layout_month = []
        for network_tariff_peak, network_tariff_off_peak in zip(network_tariffs_peak, network_tariffs_off_peak):
            # start scheduling
            charge_ev_day_period, minizinc_outputs \
                = ev.schedule_evs(num_days, num_periods_day, peak_periods, off_peak_periods, num_evs,
                                  max_charge, total_energy, prices_2d, loads_2d,
                                  network_tariff_peak, network_tariff_off_peak)
            max_demand_peak = minizinc_outputs["max_demand_peak"]
            max_demand_off_peak = minizinc_outputs["max_demand_off_peak"]
            minizinc_outputs_year["Result"] = list(minizinc_outputs.keys())
            minizinc_outputs_year[month] = [x[0] for x in list(minizinc_outputs.values())]
            print(f"{month} scheduled.")

            # merge data together
            merged_data_dict \
                = merge_results(num_days, charge_ev_day_period, loads_month, prices_month, datetime_month,
                                max_demand_peak, max_demand_off_peak, peak_periods, off_peak_periods,
                                network_tariff_peak, network_tariff_off_peak)

            # plot monthly charge profile, the existing demand profile, the total demand profile and the prices
            figure_title = f"{month}: peak network tariff = {network_tariff_peak} $/kW, " \
                f"off peak network tariff = {network_tariff_off_peak} $/kW, " \
                f"use existing load = {use_existing_load}, " \
                f"use wholesale prices = {use_wholesale_prices}"
            p_month, data_table \
                = output.visualise_monthly_results(figure_title, month, datetime_month,
                                                   network_tariff_peak, network_tariff_off_peak,
                                                   merged_data_dict, prices_month, minizinc_outputs)
            layout_month.extend([p_month, data_table])

        tab = Panel(child=layout(layout_month, sizing_mode='scale_width'), title=month)
        tab_year.append(tab)

    # save plots
    print("Saving plots...")

    output_file(f"results/{this_date_time}-existing-{use_existing_load}-price-{use_wholesale_prices}-year.html")
    output_graph = layout(row(Tabs(tabs=tab_year)), sizing_mode="scale_width")
    save(output_graph)
    show(output_graph)
    print("Done.")


if __name__ == '__main__':

    for use_existing_load in [True]:
        for use_wholesale_prices in [True]:
            main(use_existing_load, use_wholesale_prices)
