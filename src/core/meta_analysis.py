import logging
import pandas as pd
import numpy as np
import scipy.stats as stats
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)

class EffectSizeSynthesizer:
    """Executes classical and modern meta-analytic syntheses on extracted effect sizes."""

    def __init__(self):
        pass

    def run_meta_analysis(
        self,
        df: pd.DataFrame,
        effect_col: Optional[str] = None,
        n_col: Optional[str] = None,
        var_col: Optional[str] = None
    ) -> Tuple[Dict[str, Any], pd.DataFrame]:
        """Runs fixed and random effects meta-analysis given effect sizes and sample sizes."""
        if df.empty:
            return {}, pd.DataFrame()

        # Resolve effect size column
        eff_candidates = [c for c in [effect_col, "meta_standardized_effect_d", "meta_effect_size_d", "d_i", "effect_size"] if c and c in df.columns]
        if not eff_candidates:
            logger.warning("No valid effect size column found in DataFrame.")
            return {"k": 0}, pd.DataFrame()
        actual_eff_col = eff_candidates[0]

        # Resolve sample size column
        n_candidates = [c for c in [n_col, "meta_sample_size", "n_i", "sample_size", "N"] if c and c in df.columns]
        actual_n_col = n_candidates[0] if n_candidates else None

        # Resolve variance column
        v_candidates = [c for c in [var_col, "meta_effect_variance", "v_i", "variance"] if c and c in df.columns]
        actual_v_col = v_candidates[0] if v_candidates else None

        # Filter valid rows
        analysis_df = df.dropna(subset=[actual_eff_col]).copy()
        analysis_df["d_i"] = analysis_df[actual_eff_col].astype(float)

        # Handle sample sizes and variances
        if actual_n_col:
            analysis_df["n_i"] = pd.to_numeric(analysis_df[actual_n_col], errors="coerce").fillna(30.0).astype(float)
        else:
            analysis_df["n_i"] = 30.0

        if actual_v_col and actual_v_col in analysis_df.columns:
            analysis_df["v_i"] = pd.to_numeric(analysis_df[actual_v_col], errors="coerce").fillna(
                (4.0 / analysis_df["n_i"]) + (analysis_df["d_i"]**2 / (2.0 * analysis_df["n_i"]))
            )
        else:
            analysis_df["v_i"] = (4.0 / analysis_df["n_i"]) + (analysis_df["d_i"]**2 / (2.0 * analysis_df["n_i"]))

        # Ensure variance is strictly positive
        analysis_df["v_i"] = analysis_df["v_i"].apply(lambda v: max(0.0001, v) if not np.isnan(v) else 0.1)
        analysis_df["w_i"] = 1.0 / analysis_df["v_i"]

        k = len(analysis_df)
        if k < 2:
            logger.warning(f"Not enough valid studies (k={k}) for meta-analysis.")
            return {"k": k}, analysis_df

        # --- Fixed-Effects Model (Inverse-Variance) ---
        sum_w = analysis_df["w_i"].sum()
        sum_wd = (analysis_df["w_i"] * analysis_df["d_i"]).sum()

        fe_estimate = sum_wd / sum_w if sum_w > 0 else 0
        fe_se = np.sqrt(1.0 / sum_w) if sum_w > 0 else 0
        fe_z = fe_estimate / fe_se if fe_se > 0 else 0
        fe_p = 2.0 * (1.0 - stats.norm.cdf(abs(fe_z)))
        fe_ci_lower = fe_estimate - 1.96 * fe_se
        fe_ci_upper = fe_estimate + 1.96 * fe_se

        # --- Heterogeneity ---
        q_stat = (analysis_df["w_i"] * (analysis_df["d_i"] - fe_estimate)**2).sum()
        df_q = k - 1
        q_p = 1.0 - stats.chi2.cdf(q_stat, df_q) if df_q > 0 else 1.0

        i_squared = max(0.0, 100.0 * (q_stat - df_q) / q_stat) if q_stat > 0 else 0.0
        c = sum_w - (analysis_df["w_i"]**2).sum() / sum_w if sum_w > 0 else 0
        tau_squared = max(0.0, (q_stat - df_q) / c) if c > 0 else 0.0

        # --- Random-Effects Model (DerSimonian-Laird) ---
        analysis_df["w_star_i"] = 1.0 / (analysis_df["v_i"] + tau_squared)
        sum_w_star = analysis_df["w_star_i"].sum()
        sum_w_star_d = (analysis_df["w_star_i"] * analysis_df["d_i"]).sum()

        re_estimate = sum_w_star_d / sum_w_star if sum_w_star > 0 else 0
        re_se = np.sqrt(1.0 / sum_w_star) if sum_w_star > 0 else 0
        re_z = re_estimate / re_se if re_se > 0 else 0
        re_p = 2.0 * (1.0 - stats.norm.cdf(abs(re_z)))
        re_ci_lower = re_estimate - 1.96 * re_se
        re_ci_upper = re_estimate + 1.96 * re_se

        # --- Publication Bias (Egger's Test) ---
        try:
            prec = np.sqrt(analysis_df["w_i"])
            std_eff = analysis_df["d_i"] * prec
            slope, intercept, r_value, p_value, std_err = stats.linregress(prec, std_eff)
            eggers_p = p_value
        except Exception:
            eggers_p = 1.0

        # --- Begg's Rank Correlation Test ---
        try:
            tau, beggs_p = stats.kendalltau(analysis_df["d_i"], analysis_df["v_i"])
            if np.isnan(beggs_p):
                beggs_p = 1.0
        except Exception:
            beggs_p = 1.0

        results = {
            "k_studies": k,
            "fixed_effects": {
                "estimate": fe_estimate,
                "se": fe_se,
                "z": fe_z,
                "p_value": fe_p,
                "ci_lower": fe_ci_lower,
                "ci_upper": fe_ci_upper
            },
            "random_effects": {
                "estimate": re_estimate,
                "se": re_se,
                "z": re_z,
                "p_value": re_p,
                "ci_lower": re_ci_lower,
                "ci_upper": re_ci_upper
            },
            "heterogeneity": {
                "q_stat": q_stat,
                "q_p_value": q_p,
                "i_squared_pct": i_squared,
                "tau_squared": tau_squared
            },
            "publication_bias": {
                "eggers_p_value": eggers_p,
                "beggs_p_value": beggs_p
            }
        }

        return results, analysis_df

    def run_subgroup_analysis(
        self,
        df: pd.DataFrame,
        group_col: str,
        effect_col: Optional[str] = None,
        n_col: Optional[str] = None,
        var_col: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Conducts categorical subgroup meta-analysis and tests for subgroup differences (Q_between).
        """
        if df.empty or group_col not in df.columns:
            return {"subgroups": {}, "q_between": 0.0, "p_between": 1.0, "df_between": 0}

        subgroup_results = {}
        total_q_w = 0.0
        df_q_w = 0

        # Run overall first
        overall_res, _ = self.run_meta_analysis(df, effect_col=effect_col, n_col=n_col, var_col=var_col)
        q_total = overall_res.get("heterogeneity", {}).get("q_stat", 0.0)

        groups = [g for g in df[group_col].dropna().unique() if str(g).strip()]

        for g in groups:
            sub_df = df[df[group_col] == g]
            if len(sub_df) < 1:
                continue
            res, _ = self.run_meta_analysis(sub_df, effect_col=effect_col, n_col=n_col, var_col=var_col)
            subgroup_results[str(g)] = res
            sub_q = res.get("heterogeneity", {}).get("q_stat", 0.0)
            sub_k = res.get("k_studies", 0)
            total_q_w += sub_q
            df_q_w += max(0, sub_k - 1)

        # Between-group heterogeneity test
        q_between = max(0.0, q_total - total_q_w)
        df_between = max(0, len(subgroup_results) - 1)
        p_between = 1.0 - stats.chi2.cdf(q_between, df_between) if df_between > 0 else 1.0

        return {
            "subgroups": subgroup_results,
            "q_between": q_between,
            "df_between": df_between,
            "p_between": p_between
        }

    def run_meta_regression(
        self,
        df: pd.DataFrame,
        moderator_col: str,
        effect_col: Optional[str] = None,
        n_col: Optional[str] = None,
        var_col: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Weighted least-squares meta-regression assessing the effect of a continuous moderator on study effect sizes.
        """
        _, clean_df = self.run_meta_analysis(df, effect_col=effect_col, n_col=n_col, var_col=var_col)
        if clean_df.empty or moderator_col not in clean_df.columns:
            return {"k": 0, "beta": 0.0, "p_value": 1.0, "r_squared": 0.0}

        sub = clean_df.dropna(subset=["d_i", "w_star_i", moderator_col]).copy()
        sub["mod"] = pd.to_numeric(sub[moderator_col], errors="coerce")
        sub = sub.dropna(subset=["mod"])

        k = len(sub)
        if k < 3:
            logger.warning(f"Not enough studies (k={k}) for meta-regression.")
            return {"k": k, "beta": 0.0, "p_value": 1.0, "r_squared": 0.0}

        x = sub["mod"].values
        y = sub["d_i"].values
        w = sub.get("w_star_i", sub.get("w_i", pd.Series(np.ones(k)))).values

        # Weighted Linear Regression (WLS)
        x_w_mean = np.average(x, weights=w)
        y_w_mean = np.average(y, weights=w)

        ss_xx = np.sum(w * (x - x_w_mean)**2)
        ss_xy = np.sum(w * (x - x_w_mean) * (y - y_w_mean))

        beta = ss_xy / ss_xx if ss_xx > 0 else 0.0
        alpha = y_w_mean - beta * x_w_mean

        # Residual Variance & Standard Error
        y_pred = alpha + beta * x
        residuals = y - y_pred
        ss_res = np.sum(w * (residuals**2))
        df_res = k - 2

        mse = ss_res / df_res if df_res > 0 else 0.0
        se_beta = np.sqrt(mse / ss_xx) if ss_xx > 0 else 0.0
        
        if se_beta > 1e-9:
            t_stat = beta / se_beta
            p_val = float(2.0 * (1.0 - stats.t.cdf(abs(t_stat), df=df_res))) if df_res > 0 else 1.0
        elif abs(beta) > 1e-9:
            # Perfect deterministic fit with non-zero slope
            t_stat = np.inf if beta > 0 else -np.inf
            p_val = 0.0001
        else:
            t_stat = 0.0
            p_val = 1.0

        # R-squared analog
        ss_tot = np.sum(w * (y - y_w_mean)**2)
        r2 = max(0.0, 1.0 - (ss_res / ss_tot)) if ss_tot > 0 else 0.0

        return {
            "k_studies": k,
            "intercept": float(alpha),
            "beta": float(beta),
            "se_beta": float(se_beta),
            "t_statistic": float(t_stat),
            "p_value": float(p_val),
            "r_squared": float(r2)
        }

    def run_trim_and_fill(
        self,
        df: pd.DataFrame,
        effect_col: Optional[str] = None,
        n_col: Optional[str] = None,
        var_col: Optional[str] = None,
        side: str = "auto"
    ) -> Dict[str, Any]:
        """
        Duval and Tweedie's non-parametric trim-and-fill method.
        Estimates the number of missing/suppressed studies due to publication bias and
        computes the adjusted pooled effect size by imputing mirror symmetric studies.
        """
        initial_res, clean_df = self.run_meta_analysis(df, effect_col=effect_col, n_col=n_col, var_col=var_col)
        if clean_df.empty or len(clean_df) < 3:
            return {"k0_missing": 0, "adjusted_estimate": initial_res.get("random_effects", {}).get("estimate", 0.0), "imputed_df": clean_df}

        theta = initial_res.get("random_effects", {}).get("estimate", 0.0)
        yi = clean_df["d_i"].values
        vi = clean_df["v_i"].values
        k = len(yi)

        # Center effect sizes around pooled theta
        diff = yi - theta
        
        # Automatically detect asymmetry side if auto
        if side == "auto":
            # If mean difference of positive vs negative is skewed
            pos_count = np.sum(diff > 0)
            neg_count = np.sum(diff < 0)
            target_side = "left" if pos_count >= neg_count else "right"
        else:
            target_side = side.lower()

        # Ranks of absolute centered effects
        abs_diff = np.abs(diff)
        ranks = stats.rankdata(abs_diff)
        
        # Calculate Wilcoxon test-like statistic S_R
        if target_side == "left":
            # Missing studies on the left (suppressed negative/null findings)
            sign = np.where(diff > 0, 1, 0)
        else:
            sign = np.where(diff < 0, 1, 0)

        s_val = np.sum(ranks * sign)
        
        # L0 estimator of missing studies
        l0 = max(0, int(np.round((4.0 * s_val - k * (k + 1.0)) / (2.0 * k - 1.0))))
        k0 = min(l0, k)  # Upper bounded by study count

        imputed_rows = []
        if k0 > 0:
            # Sort by distance from theta on the asymmetric side
            if target_side == "left":
                extreme_indices = np.argsort(-diff)[:k0]
            else:
                extreme_indices = np.argsort(diff)[:k0]

            for idx in extreme_indices:
                orig_y = yi[idx]
                orig_v = vi[idx]
                mirror_y = 2.0 * theta - orig_y
                imputed_rows.append({
                    "d_i": float(mirror_y),
                    "v_i": float(orig_v),
                    "is_imputed": True,
                    "Authors": f"Imputed Study (Mirror {idx+1})",
                    "Year": "Imputed"
                })

        imputed_df = clean_df.copy()
        imputed_df["is_imputed"] = False
        if imputed_rows:
            imp_df_part = pd.DataFrame(imputed_rows)
            imputed_df = pd.concat([imputed_df, imp_df_part], ignore_index=True)

        # Re-estimate random effects on filled dataset
        filled_res, _ = self.run_meta_analysis(imputed_df, effect_col="d_i", var_col="v_i")

        return {
            "k_original": k,
            "k0_missing": k0,
            "side": target_side,
            "original_estimate": theta,
            "adjusted_estimate": filled_res.get("random_effects", {}).get("estimate", theta),
            "adjusted_ci_lower": filled_res.get("random_effects", {}).get("ci_lower", theta),
            "adjusted_ci_upper": filled_res.get("random_effects", {}).get("ci_upper", theta),
            "imputed_df": imputed_df
        }


