cls
clear

cd "/home/niks/Projects/solar-power-latvia"
do "codes/load_daily_data.do"

// Create output directory ONLY if it doesn't exist
cap mkdir "outputs/daily_energy_price_lp_war_dummy"

// War-start pulse dummy: 1 only on 24 Feb 2022, 0 everywhere else
gen war_start = (date == td(24feb2022))

local H = 30   // 1 month

tempname results
postfile `results' h beta se using irf_lp, replace

/***********************************************************
********** LOCAL PROJECTIONS FOR WAR-START DUMMY ***********
************************************************************/

forvalues h = 0/`H' {

    regress F`h'.d_ln_energy_price ///
        war_start ///
        L(1/14).d_ln_energy_price ///
        temperature hdd cdd wind ln_sun sun_x_solar_capacity ln_water_storage precipitation precipitation_weekly precipitation_monthly ///
        hdd_europe cdd_europe L(1/7).d_ln_energy_price_europe ///
        i.day_of_week i.month, vce(robust)

    post `results' (`h') (_b[war_start]) (_se[war_start])
}

postclose `results'

/************************************************************
************ PLOT THE IRF OF THE WAR-START SHOCK ************
************************************************************/

use irf_lp, clear

gen upper = beta + 1.96*se
gen lower = beta - 1.96*se

twoway ///
    (line beta h, lwidth(medthick)) ///
    (line upper h, lpattern(dash) lcolor(red)) ///
    (line lower h, lpattern(dash) lcolor(gray)), ///
    yline(0) ///
    xtitle("Days after war started (24 Feb 2022)") ///
    ytitle("Response of electricity price")

// Save the plot
graph export "outputs/daily_energy_price_lp_war_dummy/daily_irf_war_dummy.png", replace

// Plot the cumulative response

gen cum_beta  = sum(beta)
gen cum_upper = sum(upper)
gen cum_lower = sum(lower)

twoway ///
    (line cum_beta h, lwidth(medthick)) ///
    (line cum_upper h, lpattern(dash) lcolor(red)) ///
    (line cum_lower h, lpattern(dash) lcolor(gray)), ///
    yline(0) ///
    xtitle("Days after war started (24 Feb 2022)") ///
    ytitle("Cumulative response of electricity price") ///
    legend(order(1 "Cumulative IRF" 2 "Upper 95% CI" 3 "Lower 95% CI") pos(6) ring(0))

// Save the plot
graph export "outputs/daily_energy_price_lp_war_dummy/daily_cumulative_irf_war_dummy.png", replace
