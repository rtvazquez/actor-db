PRAGMA foreign_keys = ON;

-- =========================
-- CORE ENTITIES
-- =========================

CREATE TABLE Actors (
    actor_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    native_name TEXT, -- e.g. 石川由依
    birth_year INTEGER
);

-- Alternate spellings / romanizations / former names, so lookups resolve to one actor.
CREATE TABLE ActorAliases (
    alias_id INTEGER PRIMARY KEY,
    actor_id INTEGER NOT NULL,
    alias TEXT NOT NULL UNIQUE,

    FOREIGN KEY (actor_id)
        REFERENCES Actors(actor_id)
        ON DELETE CASCADE
);

CREATE TABLE Franchises (
    franchise_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE Studios (
    studio_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE Works (
    work_id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    release_year INTEGER,
    media_type TEXT NOT NULL
        CHECK (media_type IN ('Video Game', 'Anime', 'TV Series', 'Movie', 'OVA', 'Other')),
    franchise_id INTEGER,
    parent_work_id INTEGER,
    work_relationship_type TEXT
        CHECK (work_relationship_type IS NULL OR work_relationship_type IN
            ('Sequel', 'Prequel', 'Spin-off', 'Remake', 'Remaster', 'Side Story')),

    UNIQUE(title, release_year),

    FOREIGN KEY (franchise_id)
        REFERENCES Franchises(franchise_id)
        ON DELETE SET NULL,

    FOREIGN KEY (parent_work_id)
        REFERENCES Works(work_id)
        ON DELETE SET NULL
);

-- Bridge: which studio(s) worked on a work, and in what capacity.
-- A single work can have a developer, a publisher, an animation studio,
-- and a localization studio all at once, so this is many-to-many with a role.
CREATE TABLE WorkStudios (
    work_id INTEGER NOT NULL,
    studio_id INTEGER NOT NULL,
    studio_role TEXT NOT NULL
        CHECK (studio_role IN
            ('Developer', 'Publisher', 'Animation Studio', 'Localization Studio', 'Distributor', 'Production')),

    PRIMARY KEY (work_id, studio_id, studio_role),

    FOREIGN KEY (work_id)
        REFERENCES Works(work_id)
        ON DELETE CASCADE,

    FOREIGN KEY (studio_id)
        REFERENCES Studios(studio_id)
        ON DELETE CASCADE
);

CREATE TABLE Characters (
    character_id INTEGER PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    -- Distinguishes same-named characters from different series, e.g. "Persona 5" vs "DC".
    -- Empty string (not NULL) when no disambiguation is needed, so the UNIQUE works.
    disambiguation TEXT NOT NULL DEFAULT '',

    UNIQUE(canonical_name, disambiguation)
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
-- LANGUAGES
-- =========================

CREATE TABLE Languages (
    language_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

-- =========================
-- PERFORMANCES
-- (formerly "Roles" -- renamed and generalized so the same schema can
--  later cover live-action / motion-capture acting, not just dubbed voice work)
-- =========================

CREATE TABLE Performances (
    performance_id INTEGER PRIMARY KEY,
    appearance_id INTEGER NOT NULL,
    actor_id INTEGER NOT NULL,
    language_id INTEGER,
    performance_type TEXT NOT NULL DEFAULT 'Voice'
        CHECK (performance_type IN ('Voice', 'Live-Action', 'Motion-Capture', 'Voice+Motion-Capture')),
    role_type TEXT
        CHECK (role_type IS NULL OR role_type IN ('Main', 'Supporting', 'Minor', 'Cameo')),
    source_url TEXT, -- optional citation for where this credit was verified
    verified INTEGER NOT NULL DEFAULT 0 CHECK (verified IN (0, 1)), -- 1 = checked against a source

    UNIQUE(appearance_id, actor_id, language_id, performance_type),

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
CREATE INDEX idx_work_franchise ON Works(franchise_id);
CREATE INDEX idx_work_parent ON Works(parent_work_id);

CREATE INDEX idx_workstudios_studio ON WorkStudios(studio_id);

CREATE INDEX idx_character_name ON Characters(canonical_name);

CREATE INDEX idx_appearance_character ON CharacterAppearances(character_id);
CREATE INDEX idx_appearance_work ON CharacterAppearances(work_id);

CREATE INDEX idx_performance_actor ON Performances(actor_id);
CREATE INDEX idx_performance_appearance ON Performances(appearance_id);
