CREATE TABLE SPRING_SESSION (
    primary_id CHAR(36) NOT NULL,
    session_id CHAR(36) NOT NULL,
    creation_time BIGINT NOT NULL,
    last_access_time BIGINT NOT NULL,
    max_inactive_interval INT NOT NULL,
    expiry_time BIGINT NOT NULL,
    principal_name VARCHAR(100),
    CONSTRAINT pk_spring_session PRIMARY KEY (primary_id),
    CONSTRAINT uq_spring_session_id UNIQUE (session_id)
);

CREATE INDEX IX_SPRING_SESSION_EXPIRY
    ON SPRING_SESSION (expiry_time);

CREATE INDEX IX_SPRING_SESSION_PRINCIPAL
    ON SPRING_SESSION (principal_name);

CREATE TABLE SPRING_SESSION_ATTRIBUTES (
    session_primary_id CHAR(36) NOT NULL,
    attribute_name VARCHAR(200) NOT NULL,
    attribute_bytes LONGBLOB NOT NULL,
    CONSTRAINT pk_spring_session_attributes
        PRIMARY KEY (session_primary_id, attribute_name),
    CONSTRAINT fk_spring_session_attributes
        FOREIGN KEY (session_primary_id)
        REFERENCES SPRING_SESSION (primary_id)
        ON DELETE CASCADE
);
