"""ICD-10 diagnosis catalog (D5).

Kenyan facilities code diagnoses against the WHO ICD-10 category set (3-4
character codes such as ``B54`` for malaria), not the more granular US
ICD-10-CM leaf codes. This module bundles a curated reference of the codes
that make up the bulk of Kenyan outpatient and inpatient morbidity so the
diagnosis field can offer type-ahead search, auto-fill the canonical
description on select, and reject free-text that is not a real ICD-10 code.

ICD-10 is a global standard and identical across facilities, so — unlike the
facility-priced lab catalog — this needs no database table or per-facility
seeding. It is served in-memory.
"""

from __future__ import annotations

# code -> canonical description. Codes are normalized to uppercase, no spaces.
# Curated from the WHO ICD-10 category set for the common Kenyan disease
# burden (MOH 705 outpatient morbidity + common inpatient diagnoses).
ICD10_CODES: dict[str, str] = {
    # ── Infectious & parasitic (A00-B99) ────────────────────────────────
    "A00.9": "Cholera, unspecified",
    "A01.0": "Typhoid fever",
    "A02.0": "Salmonella enteritis",
    "A03.9": "Shigellosis, unspecified",
    "A06.0": "Acute amoebic dysentery",
    "A09": "Diarrhoea and gastroenteritis of presumed infectious origin",
    "A15.0": "Tuberculosis of lung, confirmed",
    "A15.9": "Respiratory tuberculosis, unspecified",
    "A16.9": "Respiratory tuberculosis, not confirmed",
    "A23.9": "Brucellosis, unspecified",
    "A39.0": "Meningococcal meningitis",
    "A41.9": "Sepsis, unspecified organism",
    "A51.0": "Primary genital syphilis",
    "A53.9": "Syphilis, unspecified",
    "A54.9": "Gonococcal infection, unspecified",
    "A56.9": "Chlamydial infection, unspecified",
    "A63.0": "Anogenital (venereal) warts",
    "A90": "Dengue fever",
    "B01.9": "Varicella (chickenpox) without complication",
    "B05.9": "Measles without complication",
    "B15.9": "Hepatitis A without hepatic coma",
    "B16.9": "Acute hepatitis B without delta-agent and without hepatic coma",
    "B18.1": "Chronic viral hepatitis B without delta-agent",
    "B19.9": "Unspecified viral hepatitis without hepatic coma",
    "B20": "Human immunodeficiency virus [HIV] disease",
    "B24": "Unspecified human immunodeficiency virus [HIV] disease",
    "B26.9": "Mumps without complication",
    "B34.9": "Viral infection, unspecified",
    "B35.9": "Dermatophytosis, unspecified",
    "B37.9": "Candidiasis, unspecified",
    "B50.9": "Plasmodium falciparum malaria, unspecified",
    "B51.9": "Plasmodium vivax malaria without complication",
    "B52.9": "Plasmodium malariae malaria without complication",
    "B53.8": "Other malaria, not elsewhere classified",
    "B54": "Unspecified malaria",
    "B76.9": "Hookworm disease, unspecified",
    "B77.9": "Ascariasis, unspecified",
    "B82.9": "Intestinal parasitism, unspecified",
    "B86": "Scabies",
    # ── Neoplasms (C00-D48) ─────────────────────────────────────────────
    "C34.9": "Malignant neoplasm of bronchus or lung, unspecified",
    "C50.9": "Malignant neoplasm of breast, unspecified",
    "C53.9": "Malignant neoplasm of cervix uteri, unspecified",
    "D24": "Benign neoplasm of breast",
    # ── Blood & immune (D50-D89) ────────────────────────────────────────
    "D50.9": "Iron deficiency anaemia, unspecified",
    "D57.1": "Sickle-cell disease without crisis",
    "D57.0": "Sickle-cell disease with crisis",
    "D64.9": "Anaemia, unspecified",
    # ── Endocrine, nutritional & metabolic (E00-E90) ────────────────────
    "E03.9": "Hypothyroidism, unspecified",
    "E10.9": "Type 1 diabetes mellitus without complications",
    "E11.9": "Type 2 diabetes mellitus without complications",
    "E14.9": "Unspecified diabetes mellitus without complications",
    "E16.2": "Hypoglycaemia, unspecified",
    "E43": "Unspecified severe protein-energy malnutrition",
    "E44.0": "Moderate protein-energy malnutrition",
    "E46": "Unspecified protein-energy malnutrition",
    "E66.9": "Obesity, unspecified",
    "E86": "Volume depletion (dehydration)",
    "E87.6": "Hypokalaemia",
    # ── Mental & behavioural (F00-F99) ──────────────────────────────────
    "F10.2": "Mental disorders due to alcohol, dependence syndrome",
    "F20.9": "Schizophrenia, unspecified",
    "F29": "Unspecified nonorganic psychosis",
    "F31.9": "Bipolar affective disorder, unspecified",
    "F32.9": "Depressive episode, unspecified",
    "F41.9": "Anxiety disorder, unspecified",
    "F43.1": "Post-traumatic stress disorder",
    # ── Nervous system (G00-G99) ────────────────────────────────────────
    "G03.9": "Meningitis, unspecified",
    "G40.9": "Epilepsy, unspecified",
    "G43.9": "Migraine, unspecified",
    # ── Eye & ear (H00-H95) ─────────────────────────────────────────────
    "H10.9": "Conjunctivitis, unspecified",
    "H25.9": "Age-related cataract, unspecified",
    "H60.9": "Otitis externa, unspecified",
    "H66.9": "Otitis media, unspecified",
    "H81.1": "Benign paroxysmal vertigo",
    # ── Circulatory (I00-I99) ───────────────────────────────────────────
    "I10": "Essential (primary) hypertension",
    "I11.9": "Hypertensive heart disease without heart failure",
    "I20.9": "Angina pectoris, unspecified",
    "I21.9": "Acute myocardial infarction, unspecified",
    "I50.9": "Heart failure, unspecified",
    "I63.9": "Cerebral infarction, unspecified",
    "I64": "Stroke, not specified as haemorrhage or infarction",
    "I84.9": "Haemorrhoids, unspecified",
    # ── Respiratory (J00-J99) ───────────────────────────────────────────
    "J00": "Acute nasopharyngitis (common cold)",
    "J01.9": "Acute sinusitis, unspecified",
    "J02.9": "Acute pharyngitis, unspecified",
    "J03.9": "Acute tonsillitis, unspecified",
    "J04.0": "Acute laryngitis",
    "J06.9": "Acute upper respiratory infection, unspecified",
    "J11.1": "Influenza with other respiratory manifestations",
    "J12.9": "Viral pneumonia, unspecified",
    "J15.9": "Bacterial pneumonia, unspecified",
    "J18.9": "Pneumonia, unspecified organism",
    "J20.9": "Acute bronchitis, unspecified",
    "J22": "Unspecified acute lower respiratory infection",
    "J30.9": "Allergic rhinitis, unspecified",
    "J40": "Bronchitis, not specified as acute or chronic",
    "J44.9": "Chronic obstructive pulmonary disease, unspecified",
    "J45.9": "Asthma, unspecified",
    # ── Digestive (K00-K93) ─────────────────────────────────────────────
    "K02.9": "Dental caries, unspecified",
    "K04.7": "Periapical abscess without sinus",
    "K05.6": "Periodontal disease, unspecified",
    "K21.9": "Gastro-oesophageal reflux disease without oesophagitis",
    "K29.7": "Gastritis, unspecified",
    "K30": "Functional dyspepsia",
    "K35.8": "Acute appendicitis, other and unspecified",
    "K40.9": "Inguinal hernia, without obstruction or gangrene",
    "K52.9": "Noninfective gastroenteritis and colitis, unspecified",
    "K59.0": "Constipation",
    "K80.2": "Calculus of gallbladder without cholecystitis",
    # ── Skin (L00-L99) ──────────────────────────────────────────────────
    "L01.0": "Impetigo",
    "L03.9": "Cellulitis, unspecified",
    "L08.9": "Local infection of skin and subcutaneous tissue, unspecified",
    "L20.9": "Atopic dermatitis, unspecified",
    "L23.9": "Allergic contact dermatitis, unspecified",
    "L30.9": "Dermatitis, unspecified",
    "L50.9": "Urticaria, unspecified",
    # ── Musculoskeletal (M00-M99) ───────────────────────────────────────
    "M06.9": "Rheumatoid arthritis, unspecified",
    "M10.9": "Gout, unspecified",
    "M13.9": "Arthritis, unspecified",
    "M25.5": "Pain in joint",
    "M54.5": "Low back pain",
    "M79.1": "Myalgia",
    # ── Genitourinary (N00-N99) ─────────────────────────────────────────
    "N39.0": "Urinary tract infection, site not specified",
    "N40": "Benign prostatic hyperplasia",
    "N73.9": "Female pelvic inflammatory disease, unspecified",
    "N92.0": "Excessive and frequent menstruation with regular cycle",
    "N94.6": "Dysmenorrhoea, unspecified",
    # ── Pregnancy, childbirth & puerperium (O00-O99) ────────────────────
    "O00.9": "Ectopic pregnancy, unspecified",
    "O03.9": "Complete or unspecified spontaneous abortion",
    "O06.4": "Unspecified abortion, incomplete",
    "O14.9": "Pre-eclampsia, unspecified",
    "O80": "Single spontaneous delivery",
    "O98.6": "Protozoal diseases complicating pregnancy (malaria)",
    "O99.0": "Anaemia complicating pregnancy, childbirth and the puerperium",
    "Z34.9": "Supervision of normal pregnancy, unspecified",
    # ── Perinatal (P00-P96) ─────────────────────────────────────────────
    "P07.3": "Preterm newborn, other",
    "P36.9": "Bacterial sepsis of newborn, unspecified",
    "P59.9": "Neonatal jaundice, unspecified",
    "Z38.0": "Single liveborn infant, born in hospital",
    # ── Symptoms & signs (R00-R99) ──────────────────────────────────────
    "R05": "Cough",
    "R10.4": "Other and unspecified abdominal pain",
    "R11.2": "Nausea with vomiting, unspecified",
    "R42": "Dizziness and giddiness",
    "R50.9": "Fever, unspecified",
    "R51": "Headache",
    "R53.83": "Fatigue",
    # ── Injury & poisoning (S00-T98) ────────────────────────────────────
    "S01.9": "Open wound of head, unspecified",
    "S61.9": "Open wound of wrist and hand, unspecified",
    "T14.9": "Injury, unspecified",
    "T30.0": "Burn of unspecified body region, unspecified degree",
    "T63.0": "Toxic effect of snake venom",
    # ── Factors influencing health status (Z00-Z99) ─────────────────────
    "U07.1": "COVID-19, virus identified",
    "Z00.0": "General adult medical examination",
    "Z21": "Asymptomatic HIV infection status",
    "Z23": "Encounter for immunization",
}


def normalize_code(code: str) -> str:
    """Normalize an ICD-10 code for lookup: uppercase, trimmed, no spaces."""
    return code.strip().upper().replace(" ", "")


def lookup_icd10(code: str) -> str | None:
    """Return the canonical description for a code, or None if unknown."""
    return ICD10_CODES.get(normalize_code(code))


def is_valid_icd10(code: str) -> bool:
    """True if the (normalized) code exists in the bundled catalog."""
    return normalize_code(code) in ICD10_CODES


def search_icd10(query: str, limit: int = 20) -> list[dict[str, str]]:
    """
    Type-ahead search over the catalog by code prefix or description substring.

    Code-prefix matches are ranked ahead of description matches so typing
    ``B54`` surfaces the exact code first.

    @param query: Search string (code fragment or description words)
    @param limit: Maximum results
    @returns List of ``{"code", "description"}`` dicts
    """
    q = query.strip().upper()
    if not q:
        return []
    q_desc = query.strip().lower()

    code_hits: list[dict[str, str]] = []
    desc_hits: list[dict[str, str]] = []
    seen: set[str] = set()

    for code, description in ICD10_CODES.items():
        if code.replace(" ", "").startswith(q):
            code_hits.append({"code": code, "description": description})
            seen.add(code)

    for code, description in ICD10_CODES.items():
        if code in seen:
            continue
        if q_desc in description.lower():
            desc_hits.append({"code": code, "description": description})

    code_hits.sort(key=lambda r: r["code"])
    desc_hits.sort(key=lambda r: r["description"])
    return (code_hits + desc_hits)[:limit]
