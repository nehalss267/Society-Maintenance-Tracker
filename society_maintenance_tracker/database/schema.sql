CREATE TYPE user_role AS ENUM (
    'RESIDENT',
    'ADMIN'
);

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    name VARCHAR(100) NOT NULL,

    email VARCHAR(255) NOT NULL UNIQUE,

    password_hash TEXT NOT NULL,

    role user_role NOT NULL DEFAULT 'RESIDENT',

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TYPE complaint_status AS ENUM (
    'OPEN',
    'IN_PROGRESS',
    'RESOLVED'
);

CREATE TYPE complaint_priority AS ENUM (
    'LOW',
    'MEDIUM',
    'HIGH'
);

CREATE TABLE complaints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    resident_id UUID NOT NULL
        REFERENCES users(id),

    category VARCHAR(100) NOT NULL,

    description TEXT NOT NULL,

    photo_url TEXT,

    status complaint_status NOT NULL DEFAULT 'OPEN',

    priority complaint_priority NOT NULL DEFAULT 'MEDIUM',

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    resolved_at TIMESTAMP
);

CREATE TABLE complaint_status_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    complaint_id UUID NOT NULL
        REFERENCES complaints(id)
        ON DELETE CASCADE,

    status complaint_status NOT NULL,

    changed_by UUID NOT NULL
        REFERENCES users(id),

    note TEXT,

    changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE notices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    title VARCHAR(200) NOT NULL,

    content TEXT NOT NULL,

    is_important BOOLEAN NOT NULL DEFAULT FALSE,

    created_by UUID NOT NULL
        REFERENCES users(id),

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);


CREATE INDEX idx_complaints_resident
ON complaints(resident_id);

CREATE INDEX idx_complaints_status
ON complaints(status);

CREATE INDEX idx_complaints_category
ON complaints(category);

CREATE INDEX idx_complaints_created_at
ON complaints(created_at);

CREATE INDEX idx_complaint_history_complaint
ON complaint_status_history(complaint_id);

CREATE INDEX idx_notices_created_at
ON notices(created_at);