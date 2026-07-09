"""POST-HOC DIAGNOSTIC (INFERENCE, not a gate; does not alter J-N9's verdict).

Question: is the H-M5 non-recovery rate (~0.79) probe-attributable, or is it
the baseline churn of the world as measured by the same criterion?

Method: SHAM probes — identical guard, schedule, selection, and recovery
audit, but the allocation perturbation is not applied (epsilon effectively 0
at the application site only). Non-recovery of sham probes = baseline rate at
which a guard-passing healthy zone fails the same criterion r=5 steps later
with no intervention at all.
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "model"))

import probing


class ShamProbingModel(probing.ProbingPredictiveBoundaryModel):
    def _probe_allocation(self, base_alloc, zone, sign):
        return list(base_alloc)  # sham: no perturbation; guard/audit identical


def main():
    pressures = [1.0, 1.2]
    seeds = list(range(29000, 29020))
    real_nr, sham_nr = [], []
    real_n = sham_n = 0
    for pressure in pressures:
        for seed in seeds:
            params = probing.params_for_probe_variant(
                "C_full", "W6_mutation_corridor",
                scenario="J_N9_sham_diag", arm="PA",
                adversarial_pressure=pressure,
            )
            for cls, acc in ((probing.ProbingPredictiveBoundaryModel, "real"),
                             (ShamProbingModel, "sham")):
                model = cls(seed, params)
                model.run()
                audits = getattr(model, "_probe_recovery_audits", None)
                if audits is None:
                    audits = model.probe_ledger()["probe_recovery_audits"] if hasattr(model, "probe_ledger") else []
                fails = sum(1 for a in audits if not a["recovered"])
                if acc == "real":
                    real_nr.append((fails, len(audits))); real_n += len(audits)
                else:
                    sham_nr.append((fails, len(audits))); sham_n += len(audits)
    rf = sum(f for f, _ in real_nr) / max(1, real_n)
    sf = sum(f for f, _ in sham_nr) / max(1, sham_n)
    print(f"real probes : resolved={real_n:4d} non-recovery={rf:.4f}")
    print(f"sham probes : resolved={sham_n:4d} non-recovery={sf:.4f}")
    print(f"probe-attributable excess = {rf - sf:+.4f}")


if __name__ == "__main__":
    main()
