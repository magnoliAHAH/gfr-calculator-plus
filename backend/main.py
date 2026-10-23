import os
import sqlite3
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Путь к файлу БД (убираем в Docker volume, чтобы данные не стирались при перезапуске)
DB_PATH = os.getenv("DB_PATH", "/app/data/cdss.db")


def init_db():
    """Автоматическая инициализация таблиц и стартовых данных при старте"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Таблица правил дозирования
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS drug_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        drug_name TEXT NOT NULL,
        version INTEGER NOT NULL,
        min_egfr REAL NOT NULL,
        max_egfr REAL NOT NULL,
        recommended_dose TEXT NOT NULL,
        frequency_hours INTEGER NOT NULL,
        tdm_required INTEGER DEFAULT 0
    )
    """)

    # Неизменяемый журнал аудита (Audit Trail)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        user_id TEXT NOT NULL,
        patient_age INTEGER NOT NULL,
        patient_gender TEXT NOT NULL,
        creatinine_umol_l REAL NOT NULL,
        calculated_egfr REAL NOT NULL,
        drug_name TEXT NOT NULL,
        prescribed_dose TEXT NOT NULL,
        rule_version_used INTEGER NOT NULL
    )
    """)

    # Проверяем, есть ли правила. Если пусто — заливаем базовый формуляр
    cursor.execute("SELECT COUNT(*) FROM drug_rules")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            """
            INSERT INTO drug_rules (drug_name, version, min_egfr, max_egfr, recommended_dose, frequency_hours, tdm_required)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("Vancomycin", 1, 50.0, 200.0, "1000 mg", 12, 1),
                ("Vancomycin", 1, 30.0, 49.9, "1000 mg", 24, 1),
                ("Vancomycin", 1, 0.0, 29.9, "500 mg", 24, 1)
            ]
        )
        conn.commit()

    conn.close()


app = FastAPI(title="Hospital CDSS Minimal MVP", version="1.0.0")


@app.on_event("startup")
def startup_event():
    init_db()


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


class CalculationRequest(BaseModel):
    user_id: str = Field(..., description="Табельный номер врача")
    age: int = Field(..., gt=0, lt=120)
    gender: str = Field(..., description="'male' или 'female'")
    creatinine_umol_l: float = Field(..., gt=0, description="Креатинин в мкмоль/л")
    drug_name: str = Field(..., description="Например, 'Vancomycin'")


def calculate_ckd_epi_2021(creatinine_umol: float, age: int, gender: str) -> float:
    scr = creatinine_umol / 88.4
    if gender.lower() == 'female':
        kappa = 0.7
        alpha = -0.241 if scr <= kappa else -1.200
        gender_factor = 1.012
    else:
        kappa = 0.9
        alpha = -0.302 if scr <= kappa else -1.200
        gender_factor = 1.0
    egfr = 142 * (min(scr / kappa, 1) ** alpha) * (max(scr / kappa, 1) ** -1.200) * (0.9931 ** age) * gender_factor
    return round(egfr, 2)


@app.post("/api/v1/calculate")
def calculate_and_audit(payload: CalculationRequest):
    egfr = calculate_ckd_epi_2021(payload.creatinine_umol_l, payload.age, payload.gender)

    conn = get_db_connection()
    cursor = conn.cursor()

    # Ищем правило
    cursor.execute(
        """
        SELECT * FROM drug_rules 
        WHERE drug_name = ? AND ? >= min_egfr AND ? <= max_egfr
        ORDER BY version DESC LIMIT 1;
        """,
        (payload.drug_name, egfr, egfr)
    )
    rule = cursor.fetchone()

    if not rule:
        conn.close()
        raise HTTPException(status_code=404, detail="Правило дозирования для данного уровня СКФ не найдено.")

    prescribed_dose = f"{rule['recommended_dose']} каждые {rule['frequency_hours']} ч"

    # Пишем в лог аудита
    cursor.execute(
        """
        INSERT INTO audit_logs 
        (user_id, patient_age, patient_gender, creatinine_umol_l, calculated_egfr, drug_name, prescribed_dose, rule_version_used)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            payload.user_id,
            payload.age,
            payload.gender,
            payload.creatinine_umol_l,
            egfr,
            payload.drug_name,
            prescribed_dose,
            rule['version']
        )
    )
    conn.commit()
    conn.close()

    return {
        "status": "success",
        "calculated_egfr": egfr,
        "drug": payload.drug_name,
        "recommendation": {
            "dose": rule['recommended_dose'],
            "frequency_hours": rule['frequency_hours'],
            "tdm_required": bool(rule['tdm_required'])
        },
        "rule_version": rule['version'],
        "audit_recorded": True
    }