import numpy as np
from pandas_bokeh import *
from bokeh.layouts import layout
from bokeh.models import *
from bokeh.plotting import output_file
from datetime import datetime, date
import scripts.ev_scheduling as ev
import scripts.import_data as input
import scripts.output_data as output

now_datetime = str(datetime.now().strftime("%m-%d-%H-%M"))

# time-related parameters
start_time_day = "9:00"
end_time_day = "16:30"
num_periods_day = len(pd.date_range(start=start_time_day, end=end_time_day, freq='30Min'))
peak_periods = {14, 15}
off_peak_periods = {i for i in range(14)}

# EV-related parameters
num_evs = 1000
max_charge = 25  # kW
total_energy = 20  # kWh

# tariffs or prices-related parameters
network_tariffs_peak = [0, 15, 15, 15, 0]
network_tariffs_off_peak = [0, 15, 3, 0, 15]
network_tariffs_peak = [15]
network_tariffs_off_peak = [3]


def main(use_existing_load, use_wholesale_prices):
    # import input data
    prices_year, loads_year, months_year, datetimes_year = input.read_data(start_time_day, end_time_day, )

    # start scheduling
    tab_year = []
    for month, datetime_month, prices_month, loads_month in zip(months_year, datetimes_year, prices_year, loads_year):

        # prepare input parameters
        month = month.strftime("%Y-%m")
        num_days = len(set([x.strftime("%Y-%m-%d") for x in datetime_month]))
        num_periods = len(prices_month)
        prices_2d = input.reshape_data(prices_month, num_days, num_periods_day)
        loads_2d = input.reshape_data(loads_month, num_days, num_periods_day)

        if not use_wholesale_prices:
            prices_month = [0 for _ in range(num_periods)]
            prices_2d = [[0 for _ in range(num_periods_day)] for _ in range(num_days)]

        if not use_existing_load:
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
            print(f"{month} scheduled in {minizinc_outputs['time (ms)']}.")

            # merge result data together
            merged_data_dict \
                = output.merge_results(charge_ev_day_period, loads_month, prices_month, datetime_month,
                                       max_demand_peak, max_demand_off_peak)

            # plot monthly charge profile, the existing demand profile, the total demand profile and the prices
            figure_title = f"{month}: peak network tariff = {network_tariff_peak} $/kW, " \
                           f"off peak network tariff = {network_tariff_off_peak} $/kW, " \
                           f"use existing load = {use_existing_load}, " \
                           f"use wholesale prices = {use_wholesale_prices}"
            p_month, data_table \
                = output.visualise_monthly_results(figure_title, datetime_month,
                                                   merged_data_dict, prices_month, minizinc_outputs)
            layout_month.extend([p_month, data_table])

        tab = Panel(child=layout(layout_month, sizing_mode='scale_width'), title=month)
        tab_year.append(tab)

    # save plots
    print("Saving plots...")
    output_file(f"results/{now_datetime}-existing-{use_existing_load}-price-{use_wholesale_prices}-year.html")
    output_graph = layout(row(Tabs(tabs=tab_year)), sizing_mode="scale_width")
    save(output_graph)
    show(output_graph)
    print("Done.")


if __name__ == '__main__':

    for use_existing_load in [True]:
        for use_wholesale_prices in [True]:
            main(use_existing_load, use_wholesale_prices)
