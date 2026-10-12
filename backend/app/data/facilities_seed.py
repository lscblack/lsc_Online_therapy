"""Starter dataset of real Rwandan health facilities for the "Nearby" feature.

Coordinates are approximate (good enough for distance sorting and map links). Phone numbers are
public switchboard lines where known. This is pending verification/expansion by Health Development
Initiative; a facility's `verified_at` stays null until a human confirms it.
"""

# (name, type, district, lat, lng, phone, address, hours, services)
FACILITIES: list[tuple] = [
    # --- Referral / district hospitals (Kigali) ---
    ("University Teaching Hospital of Kigali (CHUK)", "hospital", "Nyarugenge", -1.9536, 30.0606,
     "+250788304005", "KN 4 Ave, Kigali", "24/7",
     ["emergency", "maternity", "hiv_testing", "family_planning"]),
    ("King Faisal Hospital", "hospital", "Gasabo", -1.9539, 30.0905,
     "+250788123200", "KG 544 St, Kacyiru", "24/7", ["emergency", "specialist", "maternity"]),
    ("Rwanda Military Hospital (Kanombe)", "hospital", "Kicukiro", -1.9707, 30.1347,
     "+250782555000", "Kanombe, Kigali", "24/7", ["emergency", "maternity", "hiv_testing"]),
    ("Kibagabaga Hospital", "hospital", "Gasabo", -1.9339, 30.1152,
     "+250788386036", "Kibagabaga, Kigali", "24/7",
     ["emergency", "maternity", "family_planning", "youth_friendly"]),
    ("Masaka Hospital", "hospital", "Kicukiro", -2.0167, 30.1500,
     "+250788532810", "Masaka, Kigali", "24/7", ["emergency", "maternity", "hiv_testing"]),
    ("Muhima Hospital", "hospital", "Nyarugenge", -1.9450, 30.0550,
     "+250788385026", "Muhima, Kigali", "24/7", ["maternity", "family_planning", "emergency"]),
    ("Kacyiru District Hospital", "hospital", "Gasabo", -1.9370, 30.0920,
     "+250788386900", "Kacyiru, Kigali", "24/7", ["emergency", "isange_one_stop", "gbv_support"]),
    ("Nyarugenge District Hospital", "hospital", "Nyarugenge", -1.9620, 30.0520,
     None, "Nyarugenge, Kigali", "24/7", ["emergency", "maternity"]),
    # --- Provinces ---
    ("University Teaching Hospital of Butare (CHUB)", "hospital", "Huye", -2.5970, 29.7390,
     "+250252530022", "Huye, Southern Province", "24/7", ["emergency", "specialist", "maternity"]),
    ("Ruhengeri Referral Hospital", "hospital", "Musanze", -1.4990, 29.6350,
     "+250788522000", "Musanze, Northern Province", "24/7", ["emergency", "maternity"]),
    ("Gisenyi District Hospital", "hospital", "Rubavu", -1.7020, 29.2570,
     None, "Rubavu, Western Province", "24/7", ["emergency", "maternity", "hiv_testing"]),
    ("Rwamagana Provincial Hospital", "hospital", "Rwamagana", -1.9490, 30.4350,
     None, "Rwamagana, Eastern Province", "24/7", ["emergency", "maternity"]),
    # --- Isange One Stop Centres (GBV / sexual violence support) ---
    ("Isange One Stop Centre — Kacyiru", "clinic", "Gasabo", -1.9372, 30.0922,
     "3029", "Kacyiru Police Hospital, Kigali", "24/7",
     ["isange_one_stop", "gbv_support", "sexual_violence", "counselling"]),
    ("Isange One Stop Centre — Huye", "clinic", "Huye", -2.5975, 29.7400,
     "3029", "Huye, Southern Province", "24/7", ["isange_one_stop", "gbv_support", "counselling"]),
    # --- Health centres / youth-friendly clinics ---
    ("Kimironko Health Centre", "health_center", "Gasabo", -1.9370, 30.1270,
     None, "Kimironko, Kigali", "Mon–Fri 7:00–17:00",
     ["family_planning", "hiv_testing", "youth_friendly", "antenatal"]),
    ("Remera Health Centre", "health_center", "Gasabo", -1.9560, 30.1130,
     None, "Remera, Kigali", "Mon–Fri 7:00–17:00",
     ["family_planning", "hiv_testing", "youth_friendly"]),
    ("Biryogo Health Centre", "health_center", "Nyarugenge", -1.9680, 30.0560,
     None, "Biryogo, Kigali", "Mon–Fri 7:00–17:00", ["family_planning", "antenatal"]),
    ("Gikondo Health Centre", "health_center", "Kicukiro", -1.9820, 30.0770,
     None, "Gikondo, Kigali", "Mon–Fri 7:00–17:00", ["family_planning", "hiv_testing"]),
    ("Kicukiro Health Centre", "health_center", "Kicukiro", -1.9850, 30.1010,
     None, "Kicukiro, Kigali", "Mon–Fri 7:00–17:00",
     ["family_planning", "youth_friendly", "antenatal"]),
    ("Health Development Initiative (HDI) Rwanda", "clinic", "Gasabo", -1.9510, 30.0940,
     "+250788386439", "Kigali", "Mon–Fri 8:00–17:00",
     ["youth_friendly", "srhr", "counselling", "family_planning"]),
    # --- Pharmacies ---
    ("Pharmacie Conseil", "pharmacy", "Nyarugenge", -1.9500, 30.0590,
     None, "City Centre, Kigali", "Mon–Sat 8:00–20:00", ["contraception", "medicines"]),
    ("Pharmacie La Croix du Sud", "pharmacy", "Gasabo", -1.9540, 30.0900,
     None, "Kacyiru, Kigali", "Mon–Sat 8:00–20:00", ["contraception", "medicines", "emergency_contraception"]),
    ("Pharmacie Remera", "pharmacy", "Gasabo", -1.9570, 30.1125,
     None, "Remera, Kigali", "Mon–Sat 8:00–21:00", ["contraception", "medicines"]),
    ("Pharmacie Kimironko", "pharmacy", "Gasabo", -1.9378, 30.1265,
     None, "Kimironko Market, Kigali", "Mon–Sat 8:00–20:00", ["contraception", "medicines"]),
    ("Pharmacie Nyamirambo", "pharmacy", "Nyarugenge", -1.9800, 30.0430,
     None, "Nyamirambo, Kigali", "Mon–Sat 8:00–20:00", ["contraception", "medicines"]),
    ("Pharmacie Kicukiro", "pharmacy", "Kicukiro", -1.9830, 30.1000,
     None, "Kicukiro Centre, Kigali", "Mon–Sat 8:00–20:00", ["contraception", "medicines"]),
]
