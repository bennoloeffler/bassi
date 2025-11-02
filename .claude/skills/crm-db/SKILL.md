---
name: crm-db
description: " Uses the mcp postgresql to read and write crm relevant data to the crm database:
  Its about:
  sales_opportunity (Verkaufschancen)
  person (Kontaktperson im Unternehmen)
  company_site (Ein Standort eines Unternehmens)
  event (Aktivität, TODO, ... insgesamt bilden die Aktivitäten die Historie und die Zukunft von company_site, person und sales_opportunity ab)"
---

You will probably only use those tools from postgresql mcp server:
- mcp__postgresql__read_query,
- mcp__postgresql__write_query

This is the SCHEMA you will work on:

 Hier ist das vollständige Datenbankschema:

  📊 Datenbank-Schema Übersicht

  Die Datenbank enthält 6 Tabellen für ein CRM-System:

  ---
  1. adressen (Legacy-Adresstabelle)

  Persönliche Kontaktdaten (deutschsprachig):

  | Spalte             | Typ       | Beschreibung         |
  |--------------------|-----------|----------------------|
  | id                 | INTEGER   | 🔑 Primary Key       |
  | vorname            | VARCHAR   | Vorname              |
  | nachname           | VARCHAR   | Nachname             |
  | strasse_hausnummer | VARCHAR   | Straße & Hausnummer  |
  | plz                | VARCHAR   | Postleitzahl         |
  | ort                | VARCHAR   | Ort                  |
  | email              | VARCHAR   | E-Mail               |
  | mobil              | VARCHAR   | Mobilnummer          |
  | tel                | VARCHAR   | Telefon              |
  | erstellt_am        | TIMESTAMP | Erstellungsdatum     |
  | aktualisiert_am    | TIMESTAMP | Aktualisierungsdatum |

  ---
  2. company_site (Unternehmensstandorte)

  Firmeninformationen und Standorte:

  | Spalte               | Typ       | Beschreibung             |
  |----------------------|-----------|--------------------------|
  | id                   | INTEGER   | 🔑 Primary Key           |
  | name                 | VARCHAR   | ⚠️ NOT NULL - Firmenname |
  | address_street       | VARCHAR   | Straße                   |
  | address_city         | VARCHAR   | Stadt                    |
  | address_state        | VARCHAR   | Bundesland               |
  | address_postal_code  | VARCHAR   | PLZ                      |
  | address_country      | VARCHAR   | Land                     |
  | industry             | VARCHAR   | Branche                  |
  | website              | VARCHAR   | Website                  |
  | linkedin_company_url | VARCHAR   | LinkedIn-Profil          |
  | company_size         | VARCHAR   | Unternehmensgröße        |
  | annual_revenue       | BIGINT    | Jahresumsatz             |
  | notes                | TEXT      | Notizen                  |
  | tags                 | JSONB     | Tags (JSON)              |
  | created_at           | TIMESTAMP | Erstellt am              |
  | updated_at           | TIMESTAMP | Aktualisiert am          |

  ---
  3. person (Kontaktpersonen)

  Ansprechpartner in Unternehmen:

  | Spalte          | Typ       | Beschreibung         |
  |-----------------|-----------|----------------------|
  | id              | INTEGER   | 🔑 Primary Key       |
  | name            | VARCHAR   | ⚠️ NOT NULL - Name   |
  | email           | VARCHAR   | E-Mail               |
  | phone           | VARCHAR   | Telefon              |
  | linkedin_url    | VARCHAR   | LinkedIn-Profil      |
  | company_site_id | INTEGER   | 🔗 FK → company_site |
  | job_title       | VARCHAR   | Jobtitel             |
  | department      | VARCHAR   | Abteilung            |
  | notes           | TEXT      | Notizen              |
  | tags            | JSONB     | Tags (JSON)          |
  | created_at      | TIMESTAMP | Erstellt am          |
  | updated_at      | TIMESTAMP | Aktualisiert am      |

  ---
  4. sales_opportunity (Verkaufschancen)

  Sales-Pipeline und Opportunities:

  | Spalte              | Typ       | Beschreibung             |
  |---------------------|-----------|--------------------------|
  | id                  | INTEGER   | 🔑 Primary Key           |
  | title               | VARCHAR   | ⚠️ NOT NULL - Titel      |
  | value_eur           | NUMERIC   | Wert in EUR              |
  | probability         | INTEGER   | Wahrscheinlichkeit (%)   |
  | status              | VARCHAR   | Status (default: 'open') |
  | description         | TEXT      | Beschreibung             |
  | expected_close_date | DATE      | Erwarteter Abschluss     |
  | actual_close_date   | DATE      | Tatsächlicher Abschluss  |
  | person_id           | INTEGER   | 🔗 FK → person           |
  | company_site_id     | INTEGER   | 🔗 FK → company_site     |
  | source              | VARCHAR   | Quelle                   |
  | competitors         | TEXT      | Wettbewerber             |
  | next_steps          | TEXT      | Nächste Schritte         |
  | notes               | TEXT      | Notizen                  |
  | tags                | JSONB     | Tags (JSON)              |
  | created_at          | TIMESTAMP | Erstellt am              |
  | updated_at          | TIMESTAMP | Aktualisiert am          |

  ---
  5. event (Aktivitäten/Events)

  Aktivitätsverlauf (Meetings, Calls, etc.):

  | Spalte          | Typ       | Beschreibung               |
  |-----------------|-----------|----------------------------|
  | id              | INTEGER   | 🔑 Primary Key             |
  | type            | VARCHAR   | ⚠️ NOT NULL - Event-Typ    |
  | description     | TEXT      | ⚠️ NOT NULL - Beschreibung |
  | event_date      | TIMESTAMP | ⚠️ NOT NULL - Event-Datum  |
  | person_id       | INTEGER   | 🔗 FK → person             |
  | company_site_id | INTEGER   | 🔗 FK → company_site       |
  | opportunity_id  | INTEGER   | 🔗 FK → sales_opportunity  |
  | metadata        | JSONB     | Zusatzdaten (JSON)         |
  | created_at      | TIMESTAMP | Erstellt am                |

  ---
  6. schema_migrations (System-Tabelle)

  Datenbank-Migrationen:

  | Spalte      | Typ       | Beschreibung     |
  |-------------|-----------|------------------|
  | id          | BIGINT    | Migrations-ID    |
  | applied     | TIMESTAMP | Ausführungsdatum |
  | description | VARCHAR   | Beschreibung     |

  ---
  🔗 Beziehungen (Foreign Keys)

  company_site (1) ──┬── (N) person
                     │
                     └── (N) sales_opportunity
                     │
                     └── (N) event

  person (1) ────────┬── (N) sales_opportunity
                     │
                     └── (N) event

  sales_opportunity (1) ── (N) event

  ---
  💡 Besonderheiten

  - JSONB-Felder: tags, metadata für flexible Erweiterungen
  - Timestamps: Auto-Update via CURRENT_TIMESTAMP
  - Dual-System: Alte adressen-Tabelle + neues CRM-Schema
  - Multi-Entity Events: Events können mit Person, Firma ODER Opportunity verknüpft sein
