include "globals.mzn";

% parameters
int: num_days;
set of int: DAYS = 1 .. num_days;

int: num_periods_day;
set of int: PERIODS = 1 .. num_periods_day;
set of int: PEAK_PERIODS;
set of int: OFF_PEAK_PERIODS;

int: num_evs;
set of int: EVS = 1 .. num_evs;

float: max_charge; %kW
float: total_energy; %kWh

array[DAYS, PERIODS] of float: existing_loads; %$/kWh
array[DAYS, PERIODS] of float: wholesale_prices; %$/kWh
float: network_tariff_peak; %$/kW
float: network_tariff_off_peak; %$/kW


% decision variables
array[EVS, DAYS, PERIODS] of var 0 .. max_charge: charge_strategy;
var float: max_demand_peak; 
var float: max_demand_off_peak;

% objective function
var float: wholesale_cost = sum(d in DAYS) (
    sum(p in PERIODS) (
        0.001 * wholesale_prices[d, p] * 
            (sum(e in EVS) (charge_strategy[e, d, p]) * 0.5 + existing_loads[d, p] )
     )
);

var float: network_charge = network_tariff_peak * max_demand_peak + network_tariff_off_peak * max_demand_off_peak;
var float: objective = wholesale_cost + network_charge;

% charge constraint
constraint forall (d in DAYS) (
    forall (p in PERIODS) (
        forall (e in EVS) (
            0 <= charge_strategy[e, d, p] /\ charge_strategy[e, d, p] <= max_charge
        )
    )
);

% energy constraint
constraint forall (d in DAYS) (
    forall (e in EVS) (
        sum (p in PERIODS) (charge_strategy[e, d, p] * 0.5) == 20
    )
);

% max demand auxillary variable
constraint forall (d in DAYS) (
    forall (p in PEAK_PERIODS) (
        max_demand_peak >= (sum (e in EVS) (charge_strategy[e, d, p]) + existing_loads[d, p] * 2)
    )
);

constraint forall (d in DAYS) (
    forall (p in OFF_PEAK_PERIODS) (
        max_demand_off_peak >= (sum (e in EVS) (charge_strategy[e, d, p]) + existing_loads[d, p] * 2)
    )
);

solve minimize objective;

output [
"{" ++
"\"wholesale_cost\":[" ++ show(wholesale_cost) ++ "]," ++
"\"network_charge\":["  ++ show(network_charge) ++ "]," ++
"\"max_demand_peak\":["  ++ show(max_demand_peak) ++ "]," ++
"\"max_demand_off_peak\":["  ++ show(max_demand_off_peak) ++ "]," ++
"}"
];

% output 
% [show(charge_strategy[d, e, p]) ++ ", " ++ 
%     if p == num_periods_day then "EV " ++ show(e) ++ "\n" else "" endif ++
%     if p == num_periods_day  /\ e == num_evs then "---------- Day " ++ show(d) ++ " charging strategy above ----------\n\n" else "" endif 
%     |d in DAYS, e in EVS, p in PERIODS];

% output
% [
%     "max_demand = " ++ show(max_demand) ++ "\n" ++
%      "wholesale_cost = " ++ show(wholesale_cost) ++ "\n" ++
%     "network_charge = " ++ show(network_charge)
% ];




