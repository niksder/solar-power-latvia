cls
clear

cd "/home/niks/Projects/solar-power-latvia"
do "codes/panel_regressions/load_daily_data.do"

cap mkdir "outputs/panel/solar_diff_and_diff/solanka"

// =============================================================================
// TREATMENT VARIABLE: pre-war gas share (Feb 23 2022, last day before invasion)
// gas_share is available from load_daily_data.do
// =============================================================================

// Pre-war gas share: value on Feb 23 2022 (fixed treatment intensity per bzone)
gen _tmp = gas_share if date == td(23feb2022)
bysort bzone_id: egen gas_share_pre = max(_tmp)
drop _tmp
label var gas_share_pre "Gas share on Feb 23 2022 (pre-war, 0–1)"

// Scale to percentage points for readable coefficients
gen gas_share_pre_pct = gas_share_pre * 100
label var gas_share_pre_pct "Gas share on Feb 23 2022 (%)"

// all sources: gas_share brown_coal_share coal_gas_share hard_coal_share oil_share oil_shale_share peat_share hydro_ps_share hydro_ror_share hydro_wr_share wind_off_share wind_on_share
gen _tmp3 = brown_coal_share + coal_gas_share + hard_coal_share + oil_share + oil_shale_share + peat_share 
bysort bzone_id: egen fossils_share_pre = max(_tmp3)
drop _tmp3
label var fossils_share_pre "Fossil share on Feb 23 2022 (%)"

// Verify treatment values
di "Pre-war gas share by bzone:"
table bzone, statistic(mean gas_share_pre_pct)
di "Pre-war fossils share by bzone:"
table bzone, statistic(mean fossils_share_pre)

// =============================================================================
// POST-INVASION INDICATOR  (Russia invaded Ukraine Feb 24 2022)
// =============================================================================

gen post = (date >= td(24feb2022))
label var post "Post-invasion dummy (>= Feb 24 2022)"

// Log-transformed solar production
gen ln_solar = ln(solar_prod_yearly + 1)
label var ln_solar "ln(solar_prod_yearly + 1)"

// Daily log-difference of solar production (growth rate)
// D.ln_solar = ln_solar_t - ln_solar_{t-1} within each bzone
gen d_ln_solar = D.ln_solar
label var d_ln_solar "Daily log-diff of ln(solar_prod_yearly+1)"

// Drop first year of growth for bzones whose solar data appears after the
// dataset start — the rolling 365-day sum isn't a full year yet, so the
// log differences reflect data appearance, not real growth.
gen     _first_solar = date if solar_prod_yearly > 0 & !missing(solar_prod_yearly)
bysort bzone_id: egen _solar_start = min(_first_solar)
drop _first_solar
format _solar_start %td

quietly summarize date
scalar _dataset_start = r(min)

replace d_ln_solar = . if (_solar_start > _dataset_start) & (date <= _solar_start + 365)
drop _solar_start

// =============================================================================
// MAIN DiD REGRESSIONS
//   Y_it = α_i + γ_t + β*(gas_share_pre_pct_i × post_t) + weather + ε_it
//
//   α_i  = bzone fixed effects (absorbed by xtreg fe)
//   γ_t  = date fixed effects (i.date controls for all common daily shocks,
//           including seasonality; identified because weather varies
//           cross-sectionally within each day)
//   β    = DiD coefficient: extra solar output per pp of pre-war gas share
//           in the post-invasion period, relative to pre-invasion
//
//   SE clustered at bzone level (N=14; interpret CI conservatively)
// =============================================================================

// Spec 1: solar production levels (MWh)
xtreg solar_prod_yearly c.gas_share_pre_pct#i.post ///
    fossils_share_pre ///
    i.day_of_week i.month, ///
    fe vce(cluster bzone_id)
eststo did_levels

di "DiD coef (levels): " %9.3f _b[c.gas_share_pre_pct#1.post] ///
   "  SE: " %9.3f _se[c.gas_share_pre_pct#1.post]

// Spec 2: ln(solar_prod_yearly + 1) — semi-elasticity interpretation
xtreg ln_solar c.gas_share_pre_pct#i.post ///
    fossils_share_pre ///
    i.day_of_week i.month, ///
    fe vce(cluster bzone_id)
eststo did_log

di "DiD coef (log): " %9.4f _b[c.gas_share_pre_pct#1.post] ///
   "  SE: " %9.4f _se[c.gas_share_pre_pct#1.post]

// =============================================================================
// EVENT STUDY
//   Y_it = α_i + γ_t + Σ_k β_k*(gas_share_pre_pct_i × 1[hy_seq=k]) + weather + ε_it
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
// Using factor variable notation (c.gas_share_pre_pct#ib10.hy_seq_pos) causes
// Stata to pair the FE and interaction omissions: when it drops one period FE
// as redundant after within-transformation, it also drops the matching
// interaction — even if that interaction is estimable. By creating the
// interactions as plain variables, Stata sees them as standalone continuous
// regressors and applies collinearity detection independently of the period FE.
foreach k of local hy_pos_vals {
    if `k' != 8 {
        gen inter_hy`k' = gas_share_pre_pct * (hy_seq_pos == `k')
        label var inter_hy`k' "gas_share_pre_pct × (hy_seq_pos==`k')"
    }
}

local inter_vars ""
foreach k of local hy_pos_vals {
    if `k' != 8 local inter_vars "`inter_vars' inter_hy`k'"
}

// Two-way FE: bzone absorbed by xtreg fe, period absorbed by ib8.hy_seq_pos.
// ib8 sets H2 2020 as the omitted base for both FE and interactions.
// Outcome: d_ln_solar = daily log-diff (growth rate) of solar production.
xtreg d_ln_solar `inter_vars' ///
    fossils_share_pre ///
    i.month ib8.hy_seq_pos, ///
    fe vce(cluster bzone_id)
eststo event_solar_growth

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
        scalar _es_lb_`i'     = _b[inter_hy`k'] - 1.96  * _se[inter_hy`k']
        scalar _es_ub_`i'     = _b[inter_hy`k'] + 1.96  * _se[inter_hy`k']
        scalar _es_lb90_`i'   = _b[inter_hy`k'] - 1.645 * _se[inter_hy`k']
        scalar _es_ub90_`i'   = _b[inter_hy`k'] + 1.645 * _se[inter_hy`k']
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
        ytitle("Coef (daily log-diff per pp of pre-war gas share)") ///
        title("Effect of pre-war gas exposure on solar production growth rate") ///
        subtitle("DiD event study (outcome: D.ln solar); reference = H2 2020; red line = invasion Feb 24 2022") ///
        note("Two-way FE (bzone + date). Controls: sun, temperature, ln_precipitation." ///
             "SE clustered at bzone level (N = 14 bzones).", size(vsmall)) ///
        scheme(s2color)

    graph export "outputs/panel/solar_diff_and_diff/solanka/event_study_solar_production_growth_on_fossil.png", ///
        replace width(1400) height(900)

    // -------------------------------------------------------------------------
    // ACCUMULATED EFFECT PLOT
    //   Cumulative sum of event-study coefficients from the reference period.
    //   CIs use sqrt(sum of squared per-period SEs) — an approximation that
    //   assumes independence across periods (conservative if coefs are
    //   positively correlated, liberal if negatively correlated).
    // -------------------------------------------------------------------------
    gen se95      = (ub95 - lb95) / (2 * 1.96)
    gen cum_coef  = sum(coef)
    gen cum_se    = sqrt(sum(se95^2))
    gen cum_lb95  = cum_coef - 1.96  * cum_se
    gen cum_ub95  = cum_coef + 1.96  * cum_se
    gen cum_lb90  = cum_coef - 1.645 * cum_se
    gen cum_ub90  = cum_coef + 1.645 * cum_se

    twoway ///
        (rcap cum_lb95 cum_ub95 period, lcolor(navy%30)) ///
        (rcap cum_lb90 cum_ub90 period, lcolor(navy%55)) ///
        (connected cum_coef period, ///
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
        ytitle("Accumulated coef (daily log-diff per pp of pre-war gas share)") ///
        title("Accumulated effect of pre-war gas exposure on solar production growth rate") ///
        subtitle("Cumulative sum of event-study coefs; reference = H2 2020; red line = invasion Feb 24 2022") ///
        note("CIs computed as ±1.96 × sqrt(Σ SE²) — assumes independence across periods (approximation)." ///
             "SE clustered at bzone level (N = 14 bzones).", size(vsmall)) ///
        scheme(s2color)

    graph export "outputs/panel/solar_diff_and_diff/solanka/event_study_solar_production_growth_on_fossil_accumulated.png", ///
        replace width(1400) height(900)


restore

di "Done. Outputs saved to outputs/panel/solar_diff_and_diff/solanka/"

