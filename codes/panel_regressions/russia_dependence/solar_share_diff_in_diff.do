cls
clear

cd "/home/niks/Projects/solar-power-latvia"
do "codes/panel_regressions/load_daily_data.do"

// Drop NL, GR, HU, PT, ES that have higher gas share than LV
drop if bzone == "Netherlands" | bzone == "Greece" | bzone == "Hungary" | bzone == "Portugal" | bzone == "Spain" 

cap mkdir "outputs/panel/solar_diff_and_diff"

// =============================================================================
// TREATMENT VARIABLE: pre-war gas share (Feb 23 2022, last day before invasion)
// gas_share is available from load_daily_data.do
// =============================================================================

// Pre-war gas share: value on Feb 23 2022 (fixed treatment intensity per bzone)
gen _tmp = gas_share if date == td(23feb2021)
bysort bzone_id: egen gas_share_pre = max(_tmp)
drop _tmp
label var gas_share_pre "Gas share on Feb 23 2022 (pre-war, 0–1)"

// Pre-war solar share: value on Feb 23 2022 (baseline solar penetration per bzone)
gen _tmp2 = solar_share if date == td(23feb2022)
bysort bzone_id: egen solar_share_pre = max(_tmp2)
drop _tmp2
label var solar_share_pre "Solar share on Feb 23 2022 (pre-war baseline, 0–1)"

gen coal_share_pre = brown_coal_share + hard_coal_share
label var coal_share_pre "Coal share on Feb 23 2022 (%)"

// Russia dependency (constant per bzone; country-level)
bysort bzone_id: egen russia_dep_pre = mean(russia_dependency)
label var russia_dep_pre "Russia gas dependency (constant per bzone)"

// Treatment: interaction of pre-war gas share and Russia dependency
gen gas_russia_treat = gas_share_pre * russia_dep_pre
label var gas_russia_treat "gas_share_pre × russia_dep_pre (treatment intensity)"

// Verify treatment values
di "Pre-war gas share by bzone:"
table bzone, statistic(mean gas_share_pre)
di "Pre-war solar share by bzone:"
table bzone, statistic(mean solar_share_pre)
di "Pre-war coal share by bzone:"
table bzone, statistic(mean coal_share_pre)
di "Treatment (gas_share_pre × russia_dep_pre) by bzone:"
table bzone, statistic(mean gas_russia_treat)

// =============================================================================
// POST-INVASION INDICATOR  (Russia invaded Ukraine Feb 24 2022)
// =============================================================================

gen post = (date >= td(24feb2022))
label var post "Post-invasion dummy (>= Feb 24 2022)"

// =============================================================================
// MAIN DiD REGRESSIONS
//   Y_it = α_i + γ_t + β*(gas_share_pre_i × post_t) + weather + ε_it
//
//   α_i  = bzone fixed effects (absorbed by xtreg fe)
//   γ_t  = date fixed effects (i.date controls for all common daily shocks,
//           including seasonality; identified because weather varies
//           cross-sectionally within each day)
//   β    = DiD coefficient: extra solar output per unit of (gas_share_pre × russia_dep_pre)
//           in the post-invasion period, relative to pre-invasion
//
//   SE clustered at bzone level (N=14; interpret CI conservatively)
// =============================================================================

// Spec 1: solar share
xtreg solar_share c.gas_russia_treat#i.post /*solar_share_pre*/ ///
    /*i.day_of_week*/ i.month, ///
    fe vce(cluster bzone_id)
eststo did_levels
boottest c.gas_russia_treat#1.post, boottype(wild) cluster(bzone_id) reps(9999) seed(42) // Wild cluster bootstrap for robust inference with few clusters

di "DiD coef (levels): " %9.3f _b[c.gas_russia_treat#1.post] ///
   "  SE: " %9.3f _se[c.gas_russia_treat#1.post]

gen ln_solar_share = ln(solar_share + 1)
label var ln_solar_share "ln(solar_share + 1)"

// Spec 2: ln(solar_share + 1) — semi-elasticity interpretation
xtreg ln_solar_share c.gas_russia_treat#i.post /*solar_share_pre*/ ///
    /*i.day_of_week*/ i.month, ///
    fe vce(cluster bzone_id)
eststo did_log
boottest c.gas_russia_treat#1.post, boottype(wild) cluster(bzone_id) reps(9999) seed(42) // Wild cluster bootstrap for robust inference with few clusters

di "DiD coef (log): " %9.4f _b[c.gas_russia_treat#1.post] ///
   "  SE: " %9.4f _se[c.gas_russia_treat#1.post]

// =============================================================================
// EVENT STUDY
//   Y_it = α_i + γ_t + Σ_k β_k*(gas_russia_treat_i × 1[hy_seq=k]) + weather + ε_it
//
//   Reference period: H2 2020 (hy_seq_pos = 8)
//   β_k ≈ 0 for pre-war periods → parallel trends
//   β_k > 0 for post-war periods → high-gas bzones grew solar more
//
//   Period mapping (hy_seq = (year-2021)*2 + semester - 2):
//     hy_seq: -9=H1 2017, ..., -2=H2 2020 (ref), -1=H1 2021, 0=H2 2021,
//              1=H1 2022, 2=H2 2022, 3=H1 2023, ..., 8=H2 2025
//   hy_seq_pos = hy_seq + 10  (Stata factor variables must be non-negative)
//     hy_seq_pos: 1=H1 2017, ..., 8=H2 2020 (ref), 9=H1 2021, 10=H2 2021, ...
// =============================================================================

gen semester  = cond(month <= 6, 1, 2)
gen hy_seq    = (year - 2021) * 2 + semester - 2
gen hy_seq_pos = hy_seq + 10          // shift so all values are non-negative
label var hy_seq_pos "Half-year (8 = H2 2020, reference period)"

qui levelsof hy_seq_pos, local(hy_pos_vals)
di "Half-year periods in data (shifted): `hy_pos_vals'"

// Create interaction dummies manually.
// Using factor variable notation (c.gas_russia_treat#ib10.hy_seq_pos) causes
// Stata to pair the FE and interaction omissions: when it drops one period FE
// as redundant after within-transformation, it also drops the matching
// interaction — even if that interaction is estimable. By creating the
// interactions as plain variables, Stata sees them as standalone continuous
// regressors and applies collinearity detection independently of the period FE.
foreach k of local hy_pos_vals {
    if `k' != 8 {
        gen inter_hy`k' = gas_russia_treat * (hy_seq_pos == `k')
        label var inter_hy`k' "gas_russia_treat × (hy_seq_pos==`k')"
    }
}

local inter_vars ""
foreach k of local hy_pos_vals {
    if `k' != 8 local inter_vars "`inter_vars' inter_hy`k'"
}

// Two-way FE: bzone absorbed by xtreg fe, period absorbed by ib8.hy_seq_pos.
// ib8 sets H2 2020 as the omitted base for both FE and interactions.
xtreg solar_share `inter_vars' /*solar_share_pre*/ ///
    /* coal_share_pre */ ///
    /*i.day_of_week*/ i.month ib8.hy_seq_pos, ///
    fe vce(cluster bzone_id)
eststo event_solar

/*     temperature hdd cdd wind ln_sun precipitation precipitation_weekly precipitation_monthly /// // excluded since weather does not affect solar growth */

// =============================================================================
// EVENT STUDY PLOT
// =============================================================================

local nper : word count `hy_pos_vals'
local i = 1
foreach k of local hy_pos_vals {
    if `k' == 8 {
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
        // Wild cluster bootstrap CIs (Roodman et al.; same seed → reproducible)
        quietly boottest inter_hy`k', boottype(wild) cluster(bzone_id) reps(9999) seed(42) level(95) // Wild cluster bootstrap for robust inference with few clusters
        scalar _es_lb_`i'     = r(CI)[1,1]
        scalar _es_ub_`i'     = r(CI)[1,2]
        quietly boottest inter_hy`k', boottype(wild) cluster(bzone_id) reps(9999) seed(42) level(90)
        scalar _es_lb90_`i'   = r(CI)[1,1]
        scalar _es_ub90_`i'   = r(CI)[1,2]
    }
    local i = `i' + 1
}

// Extract Latvia's treatment variable (scalar survives preserve/restore)
quietly summarize gas_russia_treat if bzone == "Latvia"
scalar lv_gas_russia_treat = r(mean)
di "Latvia gas_share_pre × russia_dep_pre: " %7.4f lv_gas_russia_treat

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
        xline(2.5, lpattern(dash) lcolor(red) lwidth(medthick)) ///
        xlabel( ///
            -7 "H1 2017" -6 "H2 2017" -5 "H1 2018" -4 "H2 2018" ///
            -3 "H1 2019" -2 "H2 2019" -1 "H1 2020"  0 "H2 2020" ///
             1 "H1 2021"  2 "H2 2021"  3 "H1 2022"  4 "H2 2022" ///
             5 "H1 2023"  6 "H2 2023"  7 "H1 2024"  8 "H2 2024" ///
             9 "H1 2025" 10 "H2 2025", ///
            angle(45) labsize(small)) ///
        legend(off) ///
        xtitle("Half-year period") ///
        ytitle("Coef (% per pp of pre-war gas share)") ///
        title("Effect of pre-war gas exposure on solar share") ///
        subtitle("DiD event study; reference = H2 2020; red line = invasion Feb 24 2022") ///
        note("Two-way FE (bzone + date). Controls: sun, temperature, ln_precipitation." ///
             "SE clustered at bzone level (N = 14 bzones).", size(vsmall)) ///
        scheme(s2color)

    graph export "outputs/panel/solar_diff_and_diff/event_study_solar_share.png", ///
        replace width(1400) height(900)
    // -------------------------------------------------------------------------
    // LATVIA-SPECIFIC EFFECT: coef × Latvia's pre-war gas share
    // Interpretation: extra pp of solar share Latvia gained (vs. counterfactual
    // of zero gas dependence) relative to the H2 2020 reference period.
    // -------------------------------------------------------------------------
    local lv_gas = scalar(lv_gas_russia_treat)
    local lv_gas_fmt : di %7.4f `lv_gas'

    forvalues i = 1/`nper' {
        replace coef = _es_coef_`i'   * `lv_gas' in `i'
        replace lb95 = _es_lb_`i'    * `lv_gas' in `i'
        replace ub95 = _es_ub_`i'    * `lv_gas' in `i'
        replace lb90 = _es_lb90_`i'  * `lv_gas' in `i'
        replace ub90 = _es_ub90_`i'  * `lv_gas' in `i'
    }

    twoway ///
        (rcap lb95 ub95 period, lcolor(maroon%30)) ///
        (rcap lb90 ub90 period, lcolor(maroon%55)) ///
        (connected coef period, ///
            mcolor(maroon) lcolor(maroon) msymbol(circle) lpattern(solid)), ///
        yline(0, lpattern(dash) lcolor(gray)) ///
        xline(2.5, lpattern(dash) lcolor(red) lwidth(medthick)) ///
        xlabel( ///
            -7 "H1 2017" -6 "H2 2017" -5 "H1 2018" -4 "H2 2018" ///
            -3 "H1 2019" -2 "H2 2019" -1 "H1 2020"  0 "H2 2020" ///
             1 "H1 2021"  2 "H2 2021"  3 "H1 2022"  4 "H2 2022" ///
             5 "H1 2023"  6 "H2 2023"  7 "H1 2024"  8 "H2 2024" ///
             9 "H1 2025" 10 "H2 2025", ///
            angle(45) labsize(small)) ///
        legend(off) ///
        xtitle("Half-year period") ///
        ytitle("Extra solar share (pp) vs. zero-gas-dependence counterfactual") ///
        title("Latvia: solar share attributable to pre-war gas dependence") ///
        subtitle("DiD coefs × Latvia treatment (`lv_gas_fmt'); ref = H2 2020; red = invasion") ///
        note("Each point = estimated extra pp of solar share Latvia gained relative to a country with no pre-war gas." ///
             "Two-way FE (bzone + date). SE clustered at bzone level (N = 14 bzones).", size(vsmall)) ///
        scheme(s2color)

    graph export "outputs/panel/solar_diff_and_diff/russia_dependence/event_study_latvia_effect_solar_share.png", ///
        replace width(1400) height(900)
restore

di "Done. Outputs saved to outputs/panel/solar_diff_and_diff/russia_dependence/"

