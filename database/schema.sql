
PRAGMA foreign_keys = ON;

-- =========================
-- CORE ENTITIES
-- =========================

CREATE TABLE Actors (
    actor_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    birth_year INTEGER
);

CREATE TABLE Works (
    work_id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    release_year INTEGER,
    media_type TEXT,
    franchise TEXT,
    parent_work_id INTEGER,
    work_relationship_type TEXT,

    FOREIGN KEY (parent_work_id) REFERENCES Works(work_id)
);

CREATE TABLE Characters (
    character_id INTEGER PRIMARY KEY,
    canonical_name TEXT NOT NULL
);

-- Bridge: Character appears in a work
CREATE TABLE CharacterAppearances (
    appearance_id INTEGER PRIMARY KEY,
    character_id INTEGER NOT NULL,
    work_id INTEGER NOT NULL,

    UNIQUE(character_id, work_id),

    FOREIGN KEY (character_id)
        REFERENCES Characters(character_id)
        ON DELETE CASCADE,

    FOREIGN KEY (work_id)
        REFERENCES Works(work_id)
        ON DELETE CASCADE
);

-- =========================
-- LANGUAGES (kept in Phase 1)
-- =========================

CREATE TABLE Languages (
    language_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

-- =========================
-- VOICE ROLES
-- =========================

CREATE TABLE Roles (
    role_id INTEGER PRIMARY KEY,
    appearance_id INTEGER NOT NULL,
    actor_id INTEGER NOT NULL,
    language_id INTEGER NOT NULL,
    role_type TEXT,

    UNIQUE(appearance_id, actor_id, language_id),

    FOREIGN KEY (appearance_id)
        REFERENCES CharacterAppearances(appearance_id)
        ON DELETE CASCADE,

    FOREIGN KEY (actor_id)
        REFERENCES Actors(actor_id)
        ON DELETE RESTRICT,

    FOREIGN KEY (language_id)
        REFERENCES Languages(language_id)
        ON DELETE RESTRICT
);

-- =========================
-- INDEXES
-- =========================

CREATE INDEX idx_actor_name ON Actors(name);

CREATE INDEX idx_work_title ON Works(title);

CREATE INDEX idx_character_name ON Characters(canonical_name);

CREATE INDEX idx_appearance_character ON CharacterAppearances(character_id);

CREATE INDEX idx_appearance_work ON CharacterAppearances(work_id);

CREATE INDEX idx_role_actor ON Roles(actor_id);

CREATE INDEX idx_role_appearance ON Roles(appearance_id);