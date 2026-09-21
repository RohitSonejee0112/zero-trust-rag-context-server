-- init.sql
CREATE EXTENSION IF NOT EXISTS vector;

-- Create schema and tables
CREATE TABLE departments (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL
);

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    department_id INTEGER REFERENCES departments(id),
    clearance_level INTEGER NOT NULL DEFAULT 1 -- 1=Standard, 2=Manager, 3=Executive
);

CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    embedding vector(384),
    department_id INTEGER REFERENCES departments(id),
    sensitivity_level INTEGER NOT NULL DEFAULT 1 -- 1=Standard, 2=Confidential, 3=Secret
);

CREATE TABLE document_shares (
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    PRIMARY KEY (document_id, user_id)
);

-- Insert Departments
INSERT INTO departments (name) VALUES ('HR'), ('Engineering'), ('Finance'), ('Public');

-- Insert Users
INSERT INTO users (username, department_id, clearance_level) VALUES 
('alice_hr', 1, 2),    -- HR Manager
('david_hr', 1, 1),    -- HR Intern (Low clearance)
('bob_eng', 2, 2),     -- Eng Manager
('charlie_fin', 3, 2); -- Finance Manager

-- Insert Documents
INSERT INTO documents (title, content, department_id, sensitivity_level) VALUES
('Company Handbook', 'All employees get 20 days PTO.', 4, 1),
('HR Complaint Log', 'Alice reported Bob for stealing lunch.', 1, 1),
('Engineering Architecture', 'We are migrating to a microservices architecture using Kubernetes.', 2, 1),
('Q3 Financials', 'Revenue was up 15%, but margins decreased by 2%.', 3, 2),
('Engineering Salary Bands', 'Senior engineers make base.', 1, 1),
('Executive HR Strategy', 'We plan to lay off 10% of engineering next quarter.', 1, 3); -- Highly Sensitive HR Doc

-- Insert Explicit Shares
-- Share the HR Salary Bands document (id=5) explicitly with Charlie (Finance) even though he is not in HR
INSERT INTO document_shares (document_id, user_id) VALUES
(5, (SELECT id FROM users WHERE username = 'charlie_fin'));

-- ============================================
-- ROW LEVEL SECURITY (RLS) IMPLEMENTATION
-- ============================================

ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_shares ENABLE ROW LEVEL SECURITY;

-- App User needs to read document_shares to evaluate the policy
CREATE POLICY share_access_policy ON document_shares FOR SELECT USING (true);

-- The ABAC RLS Policy for Documents
CREATE POLICY document_access_policy ON documents
FOR SELECT
USING (
    -- Condition 1: Public Document OR (Matches Department AND User Clearance >= Document Sensitivity)
    (
        (department_id = NULLIF(current_setting('app.current_department_id', true), '')::integer OR department_id = 4)
        AND 
        (sensitivity_level <= NULLIF(current_setting('app.current_clearance_level', true), '')::integer)
    )
    OR 
    -- Condition 2: Explicit per-user override in document_shares table
    EXISTS (
        SELECT 1 FROM document_shares 
        WHERE document_shares.document_id = documents.id 
        AND document_shares.user_id = NULLIF(current_setting('app.current_user_id', true), '')::integer
    )
);

-- Create a restricted role for the application to use
DROP ROLE IF EXISTS app_user;
CREATE ROLE app_user WITH LOGIN PASSWORD 'app_password';

-- Grant access
GRANT SELECT ON documents TO app_user;
GRANT SELECT ON departments TO app_user;
GRANT SELECT ON users TO app_user;
GRANT SELECT ON document_shares TO app_user;
