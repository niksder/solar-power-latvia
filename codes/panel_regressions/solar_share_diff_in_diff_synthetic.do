cls
clear

cd "/home/niks/Projects/solar-power-latvia"
do "codes/panel_regressions/load_daily_data.do"

// Drop NL, GR, HU, PT, ES that have higher gas share than LV
drop if bzone == "Netherlands" | bzone == "Greece" | bzone == "Hungary" | bzone == "Portugal" | bzone == "Spain" 

cap mkdir "outputs/panel/solar_diff_and_diff"

// =============================================================================
// BASE VARIABLE CONSTRUCTION (computed once; shared across all program calls)
// =============================================================================

gen semester   = cond(month <= 6, 1, 2)
gen hy_seq     = (year - 2021) * 2 + semester - 2
gen hy_seq_pos = hy_seq + 10
label var hy_seq_pos "Half-year (hy_seq_pos 8 = H2 2020)"

gen ln_solar_share = ln(solar_share + 1)
label var ln_solar_share "ln(solar_share + 1)"

// Save prepared panel and bzone-name lookup as globals so the program can use them
tempfile synth_panel_tmp
save `synth_panel_tmp'
global g_synth_panel "`synth_panel_tmp'"

tempfile synth_bzones_tmp
preserve
    keep bzone_id bzone
    duplicates drop
    save `synth_bzones_tmp'
restore
global g_synth_bzones "`synth_bzones_tmp'"

// Ensure synth is installed
cap which synth
if _rc {
    di as text "Installing synth package..."
    ssc install synth, replace
}

// =============================================================================
// PROGRAM: synth_did
//
//   Runs the full synthetic-control DiD pipeline for a given treatment period.
//   Call as:  synth_did <trperiod_pos>
//
//   Argument
//     trperiod_pos  Integer hy_seq_pos value for the first post-treatment
//                   half-year (e.g. 11 = H1 2022; 6 = H2 2019).
//
//   Derived internally
//     pre_end       trperiod_pos - 1   last pre-treatment half-year for synth
//     ref_pos       trperiod_pos - 3   event-study reference period
//     post          date >= first day of half-year trperiod_pos
//     tag           e.g. "hy2022H1" or "hy2019H2"  (used in filenames)
//
//   hy_seq_pos mapping (hy_seq_pos = hy_seq + 10):
//     1=H1 2017  2=H2 2017 ... 6=H2 2019 ... 8=H2 2020 ... 11=H1 2022 ...
// =============================================================================

cap program drop synth_did
program define synth_did
    args trperiod_pos

    // ---------------------------------------------------------------
    // Derive treatment half-year metadata
    // ---------------------------------------------------------------
    local pre_end = `trperiod_pos' - 1
    local ref_pos = `trperiod_pos' - 3

    local hy_seq  = `trperiod_pos' - 10
    local sem     = mod(`hy_seq' + 1, 2) + 1            // 1=H1, 2=H2
    local yr      = (`hy_seq' + 2 - `sem') / 2 + 2021
    local mo      = cond(`sem' == 1, 1, 7)              // first month of half-year
    local hy_lbl  = cond(`sem' == 1, "H1", "H2")
    local tag     "hy`yr'`hy_lbl'"

    // Reference period label
    local ref_hy_seq = `ref_pos' - 10
    local ref_sem    = mod(`ref_hy_seq' + 1, 2) + 1
    local ref_yr     = (`ref_hy_seq' + 2 - `ref_sem') / 2 + 2021
    local ref_lbl    = cond(`ref_sem' == 1, "H1", "H2")

    // xline position on centered period axis (gap between pre_end and trperiod)
    local xline_pos = `trperiod_pos' - 8 - 0.5

    di as text ""
    di as text "================================================================="
    di as text "  synth_did: treatment = `hy_lbl' `yr'  (hy_seq_pos = `trperiod_pos')"
    di as text "  pre-match window : hy_seq_pos 1 – `pre_end'"
    di as text "  event-study ref  : hy_seq_pos `ref_pos' = `ref_lbl' `ref_yr'"
    di as text "  output tag       : `tag'"
    di as text "================================================================="

    // ---------------------------------------------------------------
    // Clean up scalars from any previous call
    // ---------------------------------------------------------------
    forvalues j = 1/100 {
        cap scalar drop _sc_id_`j'
        cap scalar drop _sc_wt_`j'
    }

    // ---------------------------------------------------------------
    // Load prepared daily panel; add post indicator
    // ---------------------------------------------------------------
    use "$g_synth_panel", clear

    local post_date_val = mdy(`mo', 1, `yr')
    gen post = (date >= `post_date_val')
    label var post "Post: date >= 01`hy_lbl'`yr'"

    quietly levelsof bzone_id if bzone == "Latvia", local(_lv_list)
    local lv_id : word 1 of `_lv_list'

    tempfile dp_run
    save `dp_run'

    // ---------------------------------------------------------------
    // Step 1: Half-year aggregation for synth
    // ---------------------------------------------------------------
    collapse (mean) gas_share solar_share energy_price ln_solar_share temperature sun precipitation population_density gdp_pps, ///
        by(bzone_id hy_seq_pos)

    // Drop donors with any missing solar_share in pre-treatment window
    bysort bzone_id: egen _n_miss_pre = total(missing(solar_share) & hy_seq_pos <= `pre_end')
    drop if _n_miss_pre > 0 & bzone_id != `lv_id'
    drop _n_miss_pre

    xtset bzone_id hy_seq_pos

    // Scale up GPP PPS for it to have bigger weight in the synth matching
    gen gdp_pps_scaled = gdp_pps * 1000
    label var gdp_pps_scaled "gdp_pps (scaled by 1000 for synth)"
    gen sun_scaled = sun / 10000
    label var sun_scaled "sun (scaled by 10000 for synth)"
    gen energy_price_scaled = energy_price * 100
    label var energy_price_scaled "energy_price (scaled by 100 for synth)"

    // ---------------------------------------------------------------
    // Predictor characteristics table (pre-treatment means per bzone)
    // ---------------------------------------------------------------
    preserve
        keep if hy_seq_pos <= `pre_end'
        collapse (mean) solar_share energy_price_scaled population_density gdp_pps_scaled sun_scaled, ///
            by(bzone_id)
        merge m:1 bzone_id using "$g_synth_bzones", nogen
        sort bzone_id
        gen byte is_treated = (bzone == "Latvia")
        order bzone is_treated solar_share energy_price_scaled population_density gdp_pps_scaled sun_scaled
        label var bzone              "Country / bidding zone"
        label var is_treated         "Treated (Latvia=1)"
        label var solar_share        "Solar share (mean, pre-treatment)"
        label var energy_price_scaled "Energy price (mean, pre-treatment, scaled)"
        label var population_density "Pop. density (mean, pre-treatment)"
        label var gdp_pps_scaled     "GDP PPS (mean, pre-treatment, scaled)"
        label var sun_scaled         "Sun radiation (mean, pre-treatment, scaled)"
        di as text ""
        di as text "=== Synth predictor characteristics by bzone (pre-treatment means) [`tag'] ==="
        list bzone is_treated solar_share energy_price_scaled population_density gdp_pps_scaled sun_scaled, ///
            noobs sep(0) clean ab(26)
        /* export delimited using ///
            "outputs/panel/solar_diff_and_diff/synth_predictors_`tag'.csv", ///
            replace
        di as text "Predictor table saved: outputs/panel/solar_diff_and_diff/synth_predictors_`tag'.csv" */
    restore

    // ---------------------------------------------------------------
    // Step 2: Run synth
    // ---------------------------------------------------------------
    
    // matrix imposedWeights = (0.10, 0.10, 0.30, 0.40, 0.10)
    // numlist imposedWeights = 0.10 0.10 0.30 0.40 0.10 

    synth solar_share ///
        solar_share(1(1)`ref_pos') ///
        energy_price_scaled(1(1)`ref_pos') population_density(1(1)`ref_pos') gdp_pps_scaled(1(1)`ref_pos') ///
        /*temperature(1(1)`ref_pos')*/ sun_scaled(1(1)`ref_pos') /*precipitation(1(1)`ref_pos')*/, ///
        trunit(`lv_id') trperiod(`trperiod_pos') ///
        customV(0.25 0.10 0.30 0.30 0.15) ///
        /*nested allopt*/

    // ---------------------------------------------------------------
    // Extract donor weights (e(W_weights) is J×2; col 2 = actual weight)
    // ---------------------------------------------------------------
    matrix _W = e(W_weights)
    local n_sc_donors = rowsof(_W)
    local _rnames : rownames _W
    local _j = 0
    foreach _rn of local _rnames {
        local _j = `_j' + 1
        scalar _sc_id_`_j' = `_rn'
        scalar _sc_wt_`_j' = _W[`_j', 2]
    }

    di as text ""
    di as text "=== Synthetic Latvia donor weights [`tag'] ==="
    di as text "  bzone                  weight"
    di as text "  ---------------------- --------"
    preserve
        use "$g_synth_bzones", clear
        forvalues j = 1/`n_sc_donors' {
            quietly levelsof bzone if bzone_id == scalar(_sc_id_`j'), local(_bname)
            local _bname_str : word 1 of `_bname'
            di as text "  " %-22s "`_bname_str'" %8.4f scalar(_sc_wt_`j')
        }
    restore

    // ---------------------------------------------------------------
    // Step 3: Apply weights to daily panel → synthetic series
    // ---------------------------------------------------------------
    use `dp_run', clear

    gen _synth_wt = 0
    forvalues j = 1/`n_sc_donors' {
        replace _synth_wt = scalar(_sc_wt_`j') if bzone_id == scalar(_sc_id_`j')
    }

    gen _wt_solar         = _synth_wt * solar_share
    gen _wt_ln_solar      = _synth_wt * ln_solar_share
    gen _wt_gas           = _synth_wt * gas_share
    gen _wt_temperature   = _synth_wt * temperature
    gen _wt_sun           = _synth_wt * sun
    gen _wt_precipitation = _synth_wt * precipitation
    gen _wt_ln_sun        = _synth_wt * ln_sun
    gen _wt_ln_precip     = _synth_wt * ln_precipitation

    preserve
        drop if bzone_id == `lv_id'
        collapse ///
            (sum)  synth_solar_share      = _wt_solar         ///
                   synth_ln_solar_share   = _wt_ln_solar       ///
                   synth_gas_share        = _wt_gas            ///
                   synth_temperature      = _wt_temperature    ///
                   synth_sun              = _wt_sun            ///
                   synth_precipitation    = _wt_precipitation  ///
                   synth_ln_sun           = _wt_ln_sun         ///
                   synth_ln_precipitation = _wt_ln_precip      ///
            (mean) post year month semester hy_seq hy_seq_pos day_of_week, ///
            by(date)
        tempfile _synth_series
        save `_synth_series'
    restore

    keep if bzone_id == `lv_id'
    merge 1:1 date using `_synth_series', nogen

    drop _synth_wt _wt_solar _wt_ln_solar _wt_gas _wt_temperature _wt_sun ///
         _wt_precipitation _wt_ln_sun _wt_ln_precip

    // ---------------------------------------------------------------
    // Path plots: Latvia (actual) vs. Synthetic Latvia
    // ---------------------------------------------------------------
    preserve
        collapse (mean) lv_solar = solar_share sc_solar = synth_solar_share ///
                        lv_gas   = gas_share   sc_gas   = synth_gas_share, ///
            by(hy_seq_pos)
        gen period = hy_seq_pos - 8

        // Solar share path
        twoway ///
            (connected sc_solar period, ///
                mcolor(gs8) lcolor(gs8) msymbol(triangle) lpattern(dash) msize(small)) ///
            (connected lv_solar period, ///
                mcolor(maroon) lcolor(maroon) msymbol(circle) lpattern(solid) msize(small)), ///
            xline(`xline_pos', lpattern(dash) lcolor(red) lwidth(medthick)) ///
            xlabel( ///
                -7 "H1 2017" -6 "H2 2017" -5 "H1 2018" -4 "H2 2018" ///
                -3 "H1 2019" -2 "H2 2019" -1 "H1 2020"  0 "H2 2020" ///
                 1 "H1 2021"  2 "H2 2021"  3 "H1 2022"  4 "H2 2022" ///
                 5 "H1 2023"  6 "H2 2023"  7 "H1 2024"  8 "H2 2024" ///
                 9 "H1 2025" 10 "H2 2025", angle(45) labsize(small)) ///
            legend(order(1 "Synthetic Latvia" 2 "Latvia (actual)") ///
                position(11) ring(0) cols(1)) ///
            xtitle("Half-year period") ///
            ytitle("Solar share (half-year mean)") ///
            title("Latvia vs. synthetic: solar share [`tag']") ///
            subtitle("Red line = treatment start (`hy_lbl' `yr')") ///
            note("Synthetic control (Abadie et al. 2010).", size(vsmall)) ///
            scheme(s2color)
        graph export "outputs/panel/solar_diff_and_diff/synth_path_solar_share_`tag'.png", ///
            replace width(1400) height(900)

        // Gas share path
        twoway ///
            (connected sc_gas period, ///
                mcolor(gs8) lcolor(gs8) msymbol(triangle) lpattern(dash) msize(small)) ///
            (connected lv_gas period, ///
                mcolor(navy) lcolor(navy) msymbol(circle) lpattern(solid) msize(small)), ///
            xline(`xline_pos', lpattern(dash) lcolor(red) lwidth(medthick)) ///
            xlabel( ///
                -7 "H1 2017" -6 "H2 2017" -5 "H1 2018" -4 "H2 2018" ///
                -3 "H1 2019" -2 "H2 2019" -1 "H1 2020"  0 "H2 2020" ///
                 1 "H1 2021"  2 "H2 2021"  3 "H1 2022"  4 "H2 2022" ///
                 5 "H1 2023"  6 "H2 2023"  7 "H1 2024"  8 "H2 2024" ///
                 9 "H1 2025" 10 "H2 2025", angle(45) labsize(small)) ///
            legend(order(1 "Synthetic Latvia" 2 "Latvia (actual)") ///
                position(1) ring(0) cols(1)) ///
            xtitle("Half-year period") ///
            ytitle("Gas share (half-year mean)") ///
            title("Latvia vs. synthetic: gas share [`tag']") ///
            subtitle("Red line = treatment start (`hy_lbl' `yr')") ///
            note("Synthetic control (Abadie et al. 2010).", size(vsmall)) ///
            scheme(s2color)
        graph export "outputs/panel/solar_diff_and_diff/synth_path_gas_share_`tag'.png", ///
            replace width(1400) height(900)
    restore

    // ---------------------------------------------------------------
    // Step 4: Construct 2-unit panel
    // ---------------------------------------------------------------
    expand 2, gen(treated)
    label var treated "Treated unit (1=Latvia, 0=Synthetic Latvia)"

    gen unit_id = treated + 1
    cap label drop _unit_lbl_`tag'
    label define _unit_lbl_`tag' 1 "Synthetic Latvia" 2 "Latvia"
    label values unit_id _unit_lbl_`tag'

    replace solar_share      = synth_solar_share      if treated == 0
    replace ln_solar_share   = synth_ln_solar_share   if treated == 0
    replace temperature      = synth_temperature      if treated == 0
    replace sun              = synth_sun              if treated == 0
    replace precipitation    = synth_precipitation    if treated == 0
    replace ln_sun           = synth_ln_sun           if treated == 0
    replace ln_precipitation = synth_ln_precipitation if treated == 0

    drop synth_solar_share synth_ln_solar_share synth_gas_share synth_temperature ///
         synth_sun synth_precipitation synth_ln_sun synth_ln_precipitation

    di as text ""
    di as text "Pre-fit check — mean solar_share by unit × pre/post:"
    table unit_id post, statistic(mean solar_share)

    gen treated_x_post = treated * post
    label var treated_x_post "Latvia × post (`tag')"

    gen month_year = year * 100 + month
    label var month_year "Year-month cluster ID"

    // ---------------------------------------------------------------
    // Main DiD regressions
    // ---------------------------------------------------------------
    regress solar_share treated_x_post treated ///
        i.day_of_week i.month, vce(cluster month_year)
    eststo did_levels_`tag'
    di "DiD coef (levels, `tag'): " %9.3f _b[treated_x_post] ///
       "  SE: " %9.3f _se[treated_x_post]

    regress ln_solar_share treated_x_post treated ///
        i.day_of_week i.month, vce(cluster month_year)
    eststo did_log_`tag'
    di "DiD coef (log,    `tag'): " %9.4f _b[treated_x_post] ///
       "  SE: " %9.4f _se[treated_x_post]

    // ---------------------------------------------------------------
    // Event study
    // ---------------------------------------------------------------
    qui levelsof hy_seq_pos, local(hy_pos_vals)

    foreach k of local hy_pos_vals {
        if `k' != `ref_pos' {
            gen inter_hy`k' = treated * (hy_seq_pos == `k')
            label var inter_hy`k' "treated × (hy_seq_pos == `k')"
        }
    }

    local inter_vars ""
    foreach k of local hy_pos_vals {
        if `k' != `ref_pos' local inter_vars "`inter_vars' inter_hy`k'"
    }

    regress solar_share `inter_vars' treated ///
        i.day_of_week ib`ref_pos'.hy_seq_pos, vce(cluster month_year)
    eststo event_solar_`tag'

    // ---------------------------------------------------------------
    // Event study plot
    // ---------------------------------------------------------------
    local nper : word count `hy_pos_vals'
    local i = 1
    foreach k of local hy_pos_vals {
        if `k' == `ref_pos' {
            scalar _es_period_`i' = `k' - 8
            scalar _es_coef_`i'   = 0
            scalar _es_lb_`i'     = 0
            scalar _es_ub_`i'     = 0
            scalar _es_lb90_`i'   = 0
            scalar _es_ub90_`i'   = 0
        }
        else {
            scalar _es_period_`i' = `k' - 8
            scalar _es_coef_`i'   = _b[inter_hy`k']
            scalar _es_lb_`i'     = _b[inter_hy`k'] - invnormal(0.975) * _se[inter_hy`k']
            scalar _es_ub_`i'     = _b[inter_hy`k'] + invnormal(0.975) * _se[inter_hy`k']
            scalar _es_lb90_`i'   = _b[inter_hy`k'] - invnormal(0.95)  * _se[inter_hy`k']
            scalar _es_ub90_`i'   = _b[inter_hy`k'] + invnormal(0.95)  * _se[inter_hy`k']
        }
        local i = `i' + 1
    }

    preserve
        clear
        set obs `nper'
        gen period = .
        gen coef   = .
        gen lb95   = .
        gen ub95   = .
        gen lb90   = .
        gen ub90   = .

        forvalues i = 1/`nper' {
            replace period = _es_period_`i' in `i'
            replace coef   = _es_coef_`i'   in `i'
            replace lb95   = _es_lb_`i'     in `i'
            replace ub95   = _es_ub_`i'     in `i'
            replace lb90   = _es_lb90_`i'   in `i'
            replace ub90   = _es_ub90_`i'   in `i'
        }

        sort period

        twoway ///
            (rcap lb95 ub95 period, lcolor(navy%30)) ///
            (rcap lb90 ub90 period, lcolor(navy%55)) ///
            (connected coef period, ///
                mcolor(navy) lcolor(navy) msymbol(circle) lpattern(solid)), ///
            yline(0, lpattern(dash) lcolor(gray)) ///
            xline(`xline_pos', lpattern(dash) lcolor(red) lwidth(medthick)) ///
            xlabel( ///
                -7 "H1 2017" -6 "H2 2017" -5 "H1 2018" -4 "H2 2018" ///
                -3 "H1 2019" -2 "H2 2019" -1 "H1 2020"  0 "H2 2020" ///
                 1 "H1 2021"  2 "H2 2021"  3 "H1 2022"  4 "H2 2022" ///
                 5 "H1 2023"  6 "H2 2023"  7 "H1 2024"  8 "H2 2024" ///
                 9 "H1 2025" 10 "H2 2025", angle(45) labsize(small)) ///
            legend(off) ///
            xtitle("Half-year period") ///
            ytitle("Solar share gap: Latvia – Synthetic Latvia (pp)") ///
            title("Event study: solar share [`tag']") ///
            subtitle("Red line = treatment start (`hy_lbl' `yr'); ref = `ref_lbl' `ref_yr'") ///
            note("Synthetic control DiD (Abadie et al. 2010). FE: unit + month + day-of-week." ///
                 "95%/90% CIs; SE clustered at month-year level.", size(vsmall)) ///
            scheme(s2color)

        graph export "outputs/panel/solar_diff_and_diff/event_study_solar_share_`tag'.png", ///
            replace width(1400) height(900)
    restore

    di as text "Done [`tag']. Outputs in outputs/panel/solar_diff_and_diff/"
end

// =============================================================================
// RUN 1 — Main analysis: treatment = H1 2022  (hy_seq_pos = 11)
// =============================================================================
synth_did 11

// =============================================================================
// RUN 2 — Placebo test: treatment = H2 2019  (hy_seq_pos = 6)
//   If the placebo DiD ≈ 0, it supports that the real effect is not driven
//   by pre-existing trends.
// =============================================================================

// synth_did 6

di as text ""
di as text "All done. Outputs saved to outputs/panel/solar_diff_and_diff/"

