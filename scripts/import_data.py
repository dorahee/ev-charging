import pandas as pd


def read_data(start_time_day, end_time_day,
              file_prices_data="data/wholesale_data.csv", file_load_data="data/load_data.csv",
              use_prices=True, include_existing_demand=True):

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
