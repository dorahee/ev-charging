import pandas as pd
import seaborn as sns
import minizinc as mzn
import numpy as np
import ast


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
wholesale_prices_months = df_prices_filtered.groupby(pd.Grouper(freq="M"))["WholesalePrice"].apply(list)

df_charge_strategies = pd.DataFrame()
for month, prices in zip(wholesale_prices_months.index.strftime('%Y-%m').tolist(), wholesale_prices_months):
    print(f"-------------------- Start scheduling EVs for {month}... --------------------")
    num_days = int(len(prices) / num_periods_day)
    prices_2d = [list(x) for x in np.reshape(prices, (num_days, num_periods_day))]

    # build a MiniZinc model
    model = mzn.Model("scenario2.mzn")
    solver = mzn.Solver.lookup("coin-bc")
    ins = mzn.Instance(solver, model)
    ins["num_days"] = num_days
    ins["num_periods_day"] = num_periods_day
    ins["num_evs"] = num_evs
    ins["max_charge"] = max_charge
    ins["total_energy"] = total_energy
    ins["wholesale_prices"] = prices_2d
    ins["network_tariff"] = network_tariff

    result = ins.solve()
    charge_strategies = result.solution.charge_strategy
    # costs = ast.literal_eval(result.solution._output_item)
    # wholesale_cost = costs["wholesale_cost"]
    # network_charge = costs["network_charge"]
    print(result.solution._output_item)
    print(f"{month} done.")

print("Done.")
