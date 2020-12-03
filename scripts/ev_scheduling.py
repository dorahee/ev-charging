import minizinc as mzn
import ast


def schedule_evs(num_days, num_periods_day, peak_periods, off_peak_periods,
                 num_evs, max_charge, total_energy,
                 prices_2d, loads_2d, network_tariff_peak, network_tariff_off_peak,
                 model_file="scripts/ev-scheduling.mzn"):

    off_peak_periods2 = {i + 1 for i in off_peak_periods}.copy()
    if network_tariff_peak == network_tariff_off_peak:
        peak_periods2 = {i + 1 for i in range(num_periods_day)}.copy()
        network_tariff_off_peak = 0
    else:
        # minizinc index starts from 1
        peak_periods2 = {i + 1 for i in peak_periods}.copy()

    # build a MiniZinc model
    model = mzn.Model(model_file)
    solver = mzn.Solver.lookup("mip")
    ins = mzn.Instance(solver, model)
    ins["num_days"] = num_days
    ins["num_periods_day"] = num_periods_day
    ins["PEAK_PERIODS"] = peak_periods2
    ins["OFF_PEAK_PERIODS"] = off_peak_periods2
    ins["num_evs"] = num_evs
    ins["max_charge"] = max_charge
    ins["total_energy"] = total_energy
    ins["wholesale_prices"] = prices_2d
    ins["network_tariff_peak"] = network_tariff_peak
    ins["network_tariff_off_peak"] = network_tariff_off_peak
    ins["existing_loads"] = loads_2d
    result = ins.solve()

    # organise results
    charge_ev_day_period = result.solution.charge_strategy
    minizinc_outputs = ast.literal_eval(result.solution._output_item)
    minizinc_outputs["time (ms)"] = [result.statistics['solveTime'].microseconds * 0.001]
    return charge_ev_day_period, minizinc_outputs
