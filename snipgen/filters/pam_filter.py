"""PAM site detection filter supporting multiple Cas variants."""

from snipgen.filters.base_filter import BaseFilter
from snipgen.models.grna_candidate import GRNACandidate
from snipgen.utils.nucleotide import expand_iupac

# Registry of supported Cas variants and their PAM configurations
PAM_REGISTRY: dict[str, dict] = {
    "SpCas9":  {"pattern": "NGG",    "position": "3prime", "length": 3},
    "SaCas9":  {"pattern": "NNGRRT", "position": "3prime", "length": 6},
    "Cpf1":    {"pattern": "TTTV",   "position": "5prime", "length": 4},
    "xCas9":   {"pattern": "NG",     "position": "3prime", "length": 2},
    "Cas9-NG": {"pattern": "NG",     "position": "3prime", "length": 2},
}


class PAMFilter(BaseFilter):
    """Validate the PAM sequence extracted alongside each candidate spacer.

    The PAM window was extracted by WindowExtractor and stored in candidate.pam.
    This filter checks whether that PAM matches the IUPAC-expanded pattern for
    the selected Cas variant.
    """

    def __init__(self, cas_variant: str = "SpCas9"):
        if cas_variant not in PAM_REGISTRY:
            supported = ", ".join(PAM_REGISTRY.keys())
            raise ValueError(
                f"Unknown Cas variant '{cas_variant}'. Supported: {supported}"
            )
        config = PAM_REGISTRY[cas_variant]
        self.cas_variant = cas_variant
        self.pam_position = config["position"]
        self.pam_length = config["length"]
        self.valid_pams: frozenset[str] = frozenset(expand_iupac(config["pattern"]))

    def apply(self, candidate: GRNACandidate) -> GRNACandidate:
        pam = candidate.pam.upper()
        # Trim or pad to expected length if necessary
        pam = pam[: self.pam_length].ljust(self.pam_length, "N")
        candidate.pam_pass = pam in self.valid_pams
        return candidate

    @property
    def name(self) -> str:
        return f"PAMFilter({self.cas_variant})"
