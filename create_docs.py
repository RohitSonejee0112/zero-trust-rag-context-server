import os

docs = [
    ('hr_complaint_log.md', 'HR Complaint Log', 1, 1, 'Alice reported Bob for stealing lunch.'),
    ('engineering_architecture.md', 'Engineering Architecture', 2, 1, 'We are migrating to a microservices architecture using Kubernetes.'),
    ('q3_financials.md', 'Q3 Financials', 3, 2, 'Revenue was up 15%, but margins decreased by 2%.'),
    ('engineering_salary_bands.md', 'Engineering Salary Bands', 1, 1, 'Senior engineers make base.'),
    ('executive_hr_strategy.md', 'Executive HR Strategy', 1, 3, 'We plan to lay off 10% of engineering next quarter.')
]

for filename, title, dept_id, sens, text in docs:
    with open(f'docs/{filename}', 'w') as f:
        f.write(f'---\ntitle: "{title}"\ndepartment_id: {dept_id}\nsensitivity_level: {sens}\n---\n\n{text}')
