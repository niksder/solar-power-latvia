cd "/home/niks/Projects/solar-power-latvia"
import delimited "data/panel_data/merged_panel_data.csv", clear

gen str_time = subinstr(time, "T", " ", 1)
replace str_time = subinstr(str_time, "Z", "", 1)
gen double ms = clock(str_time, "YMD hms")
format ms %tc

gen date = dofc(ms)
format date %td

// Drop observations before 2017-01-01 and after 2026-01-01
drop if date < td(01jan2017) | date >= td(01jan2026)

// drop if bzone == "Germany" | bzone == "Croatia" | bzone == "SE1" | bzone == "SE2" | bzone == "SE3" | bzone == "SE4" // SE missing data till 2020, Germany and Croatia missing solar data for 2016 and 2017.
// drop if bzone == "SE1" | bzone == "SE2" | bzone == "SE3" | bzone == "SE4" // SE missing data till 2020

// drop if bzone == "Germany" | bzone == "SE1" | bzone == "SE2" | bzone == "SE3" | bzone == "SE4" | bzone == "France" | bzone == "Croatia" | bzone == "Poland"

//replace gas_price = gas_price[_n-1] if gas_price == .

// Convert precipitation from m to mm (before collapse)
replace precipitation = precipitation * 1000

// Collapse to daily data
// Sum: production columns, precipitation
// Mean: everything else
collapse ///
    (sum)  gas_production ///
           solar_production ///
           total_generation precipitation ///
    (mean) energy_price gas_share solar_share gas_prod_yearly solar_prod_yearly solar_prod_growth solar_share_growth wind_u100 wind_v100 temperature sun wind ///
           precipitation_24h precipitation_weekly precipitation_monthly ///
           policy0 policy1 ///
           population_density gdp_pps ///
           year month week_of_year day_of_week, ///
    by(bzone date)

// Re-define ln variables
gen ln_energy_price = ln(energy_price)
// gen ln_gas_price = ln(gas_price)
gen ln_precipitation = ln(precipitation + 1) // Add 1 to avoid log(0)
gen ln_sun = ln(sun + 1) // Add 1 to avoid log(0)

gen hdd = cond((temperature - 273.15) < 15, 15 - (temperature - 273.15), 0)
gen cdd = cond((temperature - 273.15) > 25, (temperature - 273.15) - 25, 0)

egen bzone_id = group(bzone)
xtset bzone_id date