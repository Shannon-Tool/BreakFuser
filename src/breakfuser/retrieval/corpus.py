"""Small maintained corpus of clearly labeled reference summaries."""

from __future__ import annotations

from breakfuser.retrieval.models import SourceDocument


def _doc(
    id: str,
    title: str,
    url: str,
    excerpt: str,
    keywords: list[str],
) -> SourceDocument:
    return SourceDocument(
        id=id,
        title=title,
        url=url,
        excerpt=excerpt,
        source_type="curated_summary",
        keywords=keywords,
    )


_DOCUMENTS = [
    _doc(
        "medical-pharmacokinetics",
        "One-compartment pharmacokinetics",
        "https://www.ncbi.nlm.nih.gov/books/NBK548210/",
        "For a one-compartment IV model, half-life is ln(2) × Vd / CL. With Vd 40 L and CL 4 L/h, the result is 0.693 × 40 / 4 = 6.93 hours. Clearance determines elimination and maintenance dosing; volume of distribution primarily determines the loading dose.",
        ["pharmacokinetics", "half-life", "clearance", "volume", "loading dose", "maintenance"],
    ),
    _doc(
        "metformin-renal-label",
        "Metformin and renal function",
        "https://www.accessdata.fda.gov/drugsatfda_docs/label/2017/020357s037,020358s021,020359s025lbl.pdf",
        "Metformin labeling contraindicates use below eGFR 30 mL/min/1.73m² and recommends assessing benefit/risk between 30 and 45. Renal impairment reduces clearance and can increase metformin accumulation and lactic acidosis risk. Label and jurisdiction should be checked rather than improvising a dose.",
        ["metformin", "egfr", "renal", "kidney", "lactic acidosis"],
    ),
    _doc(
        "apixaban-ketoconazole",
        "Apixaban and strong dual CYP3A4/P-gp inhibitors",
        "https://www.accessdata.fda.gov/drugsatfda_docs/label/2021/202155s015lbl.pdf",
        "Ketoconazole and other strong dual inhibitors of CYP3A4 and P-gp can increase apixaban exposure. Label guidance distinguishes dose adjustment from an unspecified contraindication and depends on indication and inhibitor strength. Verify the exact label and obtain clinician review.",
        ["apixaban", "ketoconazole", "cyp3a4", "p-gp", "interaction"],
    ),
    _doc(
        "penicillin-allergy-history",
        "Information needed before antibiotic selection",
        "https://www.cdc.gov/antibiotic-use/hcp/clinical-guidance/",
        "Before selecting an antibiotic after a penicillin allergy report, ask about reaction symptoms and signs, timing after dosing, severity, prior beta-lactam tolerance, infection/organism, renal function, and local guidance. Do not infer a safe prescription from an incomplete allergy label.",
        ["penicillin", "allergy", "antibiotic", "reaction", "renal"],
    ),
    _doc(
        "mit-license-notices",
        "MIT license redistribution notices",
        "https://opensource.org/license/mit",
        "The MIT license requires preserving the copyright notice and permission notice in copies or substantial portions of the software. It does not impose an Apache-style NOTICE-file requirement.",
        ["mit", "license", "notice", "copyright", "apache-style"],
    ),
    _doc(
        "openssl-license-history",
        "OpenSSL and SSLeay license context",
        "https://www.openssl.org/source/license.html",
        "OpenSSL's historical licensing context includes the OpenSSL license and the original SSLeay license. Deprecation of a product or API is not the same as removal: deprecated functionality may remain available but unsupported, while removed functionality is unavailable.",
        ["openssl", "ssleay", "license", "deprecation", "removal"],
    ),
    _doc(
        "gdpr-controller-processor",
        "GDPR controller and processor roles",
        "https://eur-lex.europa.eu/eli/reg/2016/679/oj",
        "A controller determines purposes and means of processing; a processor normally acts on the controller's documented instructions. Pseudonymized user events can remain personal data. Contracts and actual processing roles can change controller/processor classification.",
        ["gdpr", "controller", "processor", "pseudonymized", "personal data"],
    ),
    _doc(
        "api-commercial-lifecycle",
        "Grandfathered plans and deprecated APIs",
        "https://semver.org/",
        "A grandfathered legacy subscription preserves a commercial plan under defined conditions. API deprecation warns of future unsupported status or removal. Continued access does not guarantee unchanged price, features, or permanence.",
        ["grandfathered", "legacy", "subscription", "deprecated", "api", "pricing"],
    ),
    _doc(
        "red-team-rules-of-engagement",
        "Authorized red-team rules of engagement",
        "https://www.crest-approved.org/membership/penetration-testing-guide/",
        "Rules of engagement should identify authorized assets and exclusions, permitted techniques, time windows, contacts, stop conditions, data handling, and evidence of authorization. Third-party dependencies and incident escalation are common omissions.",
        ["red-team", "rules", "engagement", "authorized", "scope", "roe"],
    ),
    _doc(
        "blackbox-authorization",
        "Authorized black-box evidence",
        "https://owasp.org/www-project-web-security-testing-guide/",
        "Black-box testing requires an authorized target and evidence of the defect. Login injection should be validated only against the authorized sandbox; object-level authorization requires checking ownership of the requested record. Structured evidence requests must stay within the declared scope.",
        [
            "login",
            "authentication",
            "authorization",
            "object",
            "record",
            "idor",
            "injection",
            "black-box",
        ],
    ),
    _doc(
        "influenza-estimate-uncertainty",
        "Why 1918 influenza mortality estimates vary",
        "https://www.cdc.gov/flu/pandemic-resources/1918-commemoration/index.html",
        "Mortality estimates for the 1918 influenza pandemic vary because of incomplete records, inconsistent case/death definitions, indirect estimation and extrapolation, and geographic or source-selection differences. Those limitations should be stated rather than replaced with false precision.",
        ["influenza", "1918", "mortality", "history", "estimates"],
    ),
]


class CuratedCorpusRetriever:
    def __init__(self, documents: list[SourceDocument] | None = None) -> None:
        self.documents = documents or _DOCUMENTS

    async def retrieve(self, query: str) -> list[SourceDocument]:
        normalized = " ".join(query.lower().split())
        scored: list[tuple[int, SourceDocument]] = []
        for document in self.documents:
            score = sum(keyword.lower() in normalized for keyword in document.keywords)
            if score >= 2:
                scored.append((score, document))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [document for _, document in scored[:4]]
