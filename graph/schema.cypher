CREATE CONSTRAINT concept_label IF NOT EXISTS
FOR (c:Concept) REQUIRE c.label IS UNIQUE;

CREATE INDEX concept_cui IF NOT EXISTS
FOR (c:Concept) ON (c.cui);
