"""
Ordered learning topics per skill for the deterministic 30-day roadmap (E33).
Each entry: (topic, learning task, practice task, completion criterion). Unknown skills use GENERIC.
Topics are in beginner -> intermediate order; the roadmap walks through them across a skill's days.
"""

GENERIC = [
    ("Fundamentals & vocabulary", "Study the core concepts and terminology of {s} from one structured beginner course",
     "Write a one-page cheat sheet of the 10 most important {s} concepts", "Cheat sheet covers 10 concepts in your own words"),
    ("Setting up & first steps", "Install/set up the tools for {s} and follow an official getting-started guide",
     "Complete the getting-started tutorial end to end", "Tutorial finished and working on your machine"),
    ("Core techniques", "Learn the 3-4 techniques used most often in {s} job descriptions",
     "Solve 5 small exercises using those techniques", "5 exercises solved without looking at solutions"),
    ("Applied practice", "Study a worked example of {s} applied to a realistic problem",
     "Reproduce the example with your own data/problem", "Your version runs and you can explain each step"),
    ("Intermediate topics", "Learn the next-level features of {s} (performance, best practices, common pitfalls)",
     "Refactor yesterday's work using two best practices", "Two improvements made and noted"),
    ("Mini project", "Plan a small portfolio piece that uses {s}",
     "Build the mini project and push it to GitHub with a README", "Repository with README and screenshots"),
    ("Interview readiness", "Collect 10 common interview questions on {s}",
     "Answer them out loud / in writing and fix weak spots", "10 answers written; 3 weakest revisited"),
]

S = {
    "SQL": [("SELECT, WHERE, ORDER BY", "Learn filtering and sorting queries", "Write 10 queries on a sample database (e.g. Chinook)", "10 queries return correct results"),
            ("Aggregations & GROUP BY", "Learn COUNT/SUM/AVG, GROUP BY and HAVING", "Answer 8 business questions with aggregates", "8 correct aggregate queries"),
            ("JOINs", "Learn INNER/LEFT/RIGHT/FULL joins", "Write 8 multi-table join queries", "Join results verified by row counts"),
            ("Subqueries & CTEs", "Learn subqueries and WITH (CTE) syntax", "Rewrite 4 nested queries as CTEs", "4 CTE queries produce identical results"),
            ("Window functions", "Learn ROW_NUMBER, RANK, running totals with OVER()", "Solve 5 ranking/running-total problems", "5 window-function queries correct"),
            ("Practice set", "Do a timed SQL practice set (LeetCode/HackerRank easy-medium)", "Solve 10 problems in 90 minutes", "≥ 7/10 solved"),
            ("Mini project", "Analyse a public dataset with SQL only", "Write a 1-page findings report with 5 queries", "Report + queries on GitHub")],
    "Python": [("Syntax, variables & types", "Learn Python basics (types, strings, lists, dicts)", "Write 10 small exercises", "10 exercises run without errors"),
               ("Control flow & functions", "Learn if/for/while and writing functions", "Write 5 reusable functions with docstrings", "5 functions tested with sample inputs"),
               ("Files, errors & modules", "Learn file I/O, exceptions and importing modules", "Build a script that reads a CSV and handles bad rows", "Script processes a messy CSV"),
               ("Pandas basics", "Learn DataFrames: read, select, filter, groupby", "Clean and summarise a Kaggle dataset", "Notebook with 5 summary tables"),
               ("Visualising data", "Learn matplotlib/seaborn basics", "Make 4 charts answering 4 questions", "4 labelled charts"),
               ("Mini project", "Plan a small data or automation project", "Build it and push to GitHub with a README", "Repo with README")],
    "Excel": [("Formulas & references", "Learn relative/absolute references, IF, SUMIFS, COUNTIFS", "Build a sheet with 10 formulas", "Formulas recalculate correctly"),
              ("Lookups", "Learn XLOOKUP / INDEX-MATCH", "Join two tables with lookups", "No #N/A errors on valid keys"),
              ("Pivot tables", "Learn pivot tables and slicers", "Answer 5 questions with pivots", "5 pivot tables"),
              ("Charts & dashboards", "Learn charts and a one-page dashboard layout", "Build a dashboard from a sales dataset", "Dashboard with 4 visuals"),
              ("Data cleaning", "Learn text functions, Remove Duplicates, Power Query basics", "Clean a messy dataset", "Clean table ready for analysis")],
    "Power BI": [("Interface & data import", "Learn Power BI Desktop, connecting to Excel/CSV", "Import a dataset and build a first report", "Report with 2 visuals"),
                 ("Power Query", "Learn transformations (types, merge, append, unpivot)", "Clean a messy dataset in Power Query", "Applied steps documented"),
                 ("Data modelling", "Learn star schema and relationships", "Model a fact table with 2 dimensions", "Relationships work in visuals"),
                 ("DAX basics", "Learn measures, CALCULATE, time intelligence", "Write 6 measures (YTD, % change…)", "6 measures validated"),
                 ("Dashboard design", "Learn layout, slicers, drill-through", "Build a 1-page dashboard", "Dashboard published/exported"),
                 ("PL-300 prep", "Review the PL-300 skills outline on Microsoft Learn", "Take one practice assessment", "Score recorded; weak areas listed")],
    "Tableau": [("Interface & connecting data", "Learn Tableau Public/Desktop basics", "Connect a CSV and make 3 charts", "3 charts built"),
                ("Dimensions, measures & filters", "Learn discrete/continuous fields and filters", "Build 4 filtered views", "Filters work correctly"),
                ("Calculated fields & LOD", "Learn calculations and FIXED LOD expressions", "Create 5 calculated fields", "5 calcs validated"),
                ("Dashboards & actions", "Learn dashboard layout and filter actions", "Build an interactive dashboard", "Dashboard with 2 actions"),
                ("Storytelling", "Learn Tableau Stories and chart best practices", "Publish a 4-point story on Tableau Public", "Public link works")],
    "Statistics": [("Descriptive statistics", "Learn mean, median, variance, percentiles", "Summarise a dataset by hand/Python", "Summary table matches library output"),
                   ("Distributions", "Learn normal/binomial distributions and sampling", "Simulate sampling distributions in Python", "Plots of 3 distributions"),
                   ("Probability basics", "Learn conditional probability and Bayes' rule", "Solve 8 probability problems", "≥ 6/8 correct"),
                   ("Hypothesis testing", "Learn t-tests, p-values, confidence intervals", "Run 3 tests on real data", "3 tests interpreted in plain words"),
                   ("Correlation & regression", "Learn correlation vs causation, linear regression", "Fit and interpret a regression", "Coefficients explained"),
                   ("A/B testing", "Learn experiment design and sample size", "Analyse a sample A/B test dataset", "Decision memo written")],
    "Data Visualization": [("Chart selection", "Learn which chart answers which question", "Classify 10 scenarios to chart types", "10/10 justified"),
                           ("Design principles", "Learn colour, labelling, clutter removal", "Redesign 3 bad charts", "Before/after for 3 charts"),
                           ("Building charts", "Build charts in your main tool (Excel/Power BI/Tableau/Python)", "Create 5 charts on one dataset", "5 clean charts"),
                           ("Dashboards", "Learn dashboard layout and hierarchy", "Build a 1-page dashboard", "Dashboard answers 3 questions"),
                           ("Data storytelling", "Learn to present insights as a narrative", "Present the dashboard in 3 minutes (record it)", "Recording made")],
    "Communication": [("Explaining technical work", "Learn the 'situation-insight-action' structure", "Explain one project in 5 sentences", "Peer understands it"),
                      ("Written updates", "Learn concise emails and status updates", "Write 3 status updates for a project", "Each under 120 words"),
                      ("Presenting insights", "Learn to present data to non-technical people", "Give a 3-minute presentation (record it)", "Recording reviewed with notes"),
                      ("Stakeholder questions", "Learn to ask clarifying questions and handle feedback", "Role-play 2 stakeholder meetings", "Notes of 2 sessions")],
    "Machine Learning": [("ML workflow", "Learn problem framing, train/test split, metrics", "Frame 3 problems as ML tasks", "3 framings written"),
                         ("Regression", "Learn linear regression and evaluation (MAE, RMSE)", "Train a regression model with scikit-learn", "Model + metrics in notebook"),
                         ("Classification", "Learn logistic regression, trees, precision/recall", "Train 2 classifiers and compare", "Comparison table"),
                         ("Feature engineering", "Learn encoding, scaling, leakage", "Improve a baseline with 3 features", "Metric improves"),
                         ("Model selection", "Learn cross-validation and hyperparameter tuning", "Tune one model with CV", "CV score reported"),
                         ("Mini project", "End-to-end ML project on a Kaggle dataset", "Push notebook + README to GitHub", "Repo with results")],
    "Docker": [("Containers vs VMs", "Learn images, containers, registries", "Run 3 official images", "Containers run"),
               ("Dockerfile", "Learn writing a Dockerfile", "Containerise a small app", "Image builds and runs"),
               ("Volumes & networking", "Learn volumes, ports, networks", "Run an app with a database container", "App talks to DB"),
               ("Docker Compose", "Learn multi-container apps with compose", "Write a compose file for app + DB", "docker compose up works")],
    "Kubernetes": [("Core concepts", "Learn pods, deployments, services", "Deploy an app to minikube/kind", "App reachable"),
                   ("Config & secrets", "Learn ConfigMaps and Secrets", "Externalise app config", "Config change without rebuild"),
                   ("Scaling & updates", "Learn ReplicaSets, rolling updates, probes", "Scale and roll out a new version", "Zero-downtime update"),
                   ("Helm basics", "Learn Helm charts", "Install an app with Helm", "Release installed")],
    "AWS": [("Cloud & IAM basics", "Learn regions, IAM users/roles, free tier", "Create an IAM user with least privilege", "Policy documented"),
            ("Compute: EC2", "Learn EC2, security groups, key pairs", "Launch an EC2 instance and SSH in", "Instance reachable"),
            ("Storage: S3", "Learn buckets, permissions, static hosting", "Host a static site on S3", "Site URL works"),
            ("Databases & serverless", "Learn RDS and Lambda basics", "Write one Lambda function", "Lambda runs on a test event"),
            ("Cloud Practitioner prep", "Review the AWS Cloud Practitioner exam guide", "Take one practice test", "Score recorded")],
    "Java": [("Syntax & OOP basics", "Learn classes, objects, inheritance", "Write 5 small OOP exercises", "Exercises compile and run"),
             ("Collections & generics", "Learn List/Map/Set and generics", "Solve 5 collection problems", "5 solved"),
             ("Exceptions & I/O", "Learn exception handling and file I/O", "Write a file-processing program", "Handles bad input"),
             ("Streams & lambdas", "Learn the Stream API", "Rewrite 5 loops with streams", "Same results")],
    "Spring Boot": [("Project setup", "Learn Spring Initializr and project structure", "Create a hello-world REST app", "Endpoint responds"),
                    ("REST controllers", "Learn @RestController, request mapping, DTOs", "Build CRUD endpoints", "CRUD works in Postman"),
                    ("Data JPA", "Learn repositories and entities", "Persist data to MySQL/H2", "Data saved and queried"),
                    ("Validation & errors", "Learn validation and exception handlers", "Add validation to 2 endpoints", "Bad input returns 400")],
    "Microservices": [("Architecture basics", "Learn monolith vs microservices, bounded contexts", "Split a sample app into 2 services (design)", "Diagram drawn"),
                      ("Service communication", "Learn REST/messaging between services", "Make 2 services call each other", "End-to-end call works"),
                      ("Resilience", "Learn retries, timeouts, circuit breakers", "Add a circuit breaker", "Failure handled gracefully")],
    "REST APIs": [("HTTP & REST principles", "Learn methods, status codes, resources", "Design endpoints for a small app", "API spec written"),
                  ("Building an API", "Build CRUD endpoints in your stack", "Implement 4 endpoints", "Tested with Postman"),
                  ("Auth & docs", "Learn token auth and OpenAPI docs", "Add auth + OpenAPI page", "Docs page renders")],
    "Git": [("Basics", "Learn init, add, commit, log", "Track a project with 10 commits", "Clean history"),
            ("Branching & merging", "Learn branches, merge, conflicts", "Resolve a merge conflict", "Conflict resolved"),
            ("GitHub workflow", "Learn remotes, pull requests, reviews", "Open a PR on your own repo", "PR merged")],
    "Pandas": [("DataFrames", "Learn read_csv, selecting, filtering", "Explore a dataset with 10 operations", "Notebook runs"),
               ("Cleaning", "Learn missing values, types, duplicates", "Clean a messy dataset", "No nulls in key columns"),
               ("GroupBy & merge", "Learn groupby, pivot_table, merge", "Answer 5 questions", "5 answers"),
               ("Time series", "Learn datetime handling and resampling", "Resample a daily dataset to monthly", "Monthly table")],
    "Linux": [("Shell basics", "Learn navigation, files, permissions", "Complete 20 shell exercises", "Exercises done"),
              ("Processes & services", "Learn ps, top, systemctl, logs", "Diagnose a running service", "Notes of findings"),
              ("Scripting", "Learn bash scripting basics", "Write a backup script", "Script runs via cron")],
    "Deep Learning": [("Neural network basics", "Learn perceptrons, activations, backprop", "Train an MLP on MNIST", "≥ 95% accuracy"),
                      ("CNNs", "Learn convolutional networks", "Train a CNN on CIFAR-10", "Accuracy reported"),
                      ("Transfer learning", "Learn fine-tuning pretrained models", "Fine-tune a model on a small dataset", "Improvement over baseline")],
}


def topics_for(skill: str):
    """Specific curriculum + (if it has none) a portfolio mini project + interview readiness stage."""
    generic = [tuple(x.format(s=skill) for x in t) for t in GENERIC]
    for key, items in S.items():
        if key.lower() == (skill or "").lower():
            tail = [g for g in generic[-2:] if not any(g[0].split()[0].lower() in i[0].lower() for i in items)]
            return list(items) + tail
    return generic


# E35: free, official / widely used learning resources per skill (attached to every learning day of that skill)
RESOURCES = {
    "SQL": ["SQLBolt interactive lessons: https://sqlbolt.com/", "Mode SQL tutorial: https://mode.com/sql-tutorial/"],
    "Python": ["Official Python tutorial: https://docs.python.org/3/tutorial/"],
    "Pandas": ["pandas getting started: https://pandas.pydata.org/docs/getting_started/index.html"],
    "Excel": ["Exceljet formulas & functions: https://exceljet.net/"],
    "Power BI": ["Microsoft Learn Power BI docs & training: https://learn.microsoft.com/en-us/power-bi/"],
    "Tableau": ["Tableau free training videos: https://www.tableau.com/learn/training"],
    "Statistics": ["Khan Academy statistics & probability: https://www.khanacademy.org/math/statistics-probability"],
    "Data Visualization": ["Storytelling with Data (blog & exercises): https://www.storytellingwithdata.com/"],
    "Communication": ["Toastmasters (public speaking practice): https://www.toastmasters.org/"],
    "Machine Learning": ["Google Machine Learning Crash Course: https://developers.google.com/machine-learning/crash-course"],
    "Deep Learning": ["fast.ai Practical Deep Learning: https://course.fast.ai/"],
    "Docker": ["Docker get started: https://docs.docker.com/get-started/"],
    "Kubernetes": ["Kubernetes basics tutorial: https://kubernetes.io/docs/tutorials/kubernetes-basics/"],
    "AWS": ["AWS Skill Builder (free courses): https://skillbuilder.aws/"],
    "Git": ["Pro Git book (free): https://git-scm.com/book/en/v2"],
    "Java": ["dev.java learning path: https://dev.java/learn/"],
    "Spring Boot": ["Spring guides: https://spring.io/guides"],
    "Microservices": ["microservices.io patterns: https://microservices.io/"],
    "REST APIs": ["REST API tutorial: https://restfulapi.net/"],
    "Linux": ["Linux Journey: https://linuxjourney.com/"],
}

# E35: capstone project tailored to the target role (days 29-30)
CAPSTONES = [  # E36: most specific roles first ("cybersecurity analyst" must not match the generic "analyst")
    (("security", "cyber", "soc ", "penetration", "ethical hacker"),
     "Set up a small lab, run a vulnerability assessment{using}, and write an incident-style report with fixes ranked by risk"),
    (("data engineer", "etl", "big data", "pipeline"),
     "Build a batch data pipeline: ingest a public dataset, transform and load it into a warehouse table{using}, schedule it and document data quality checks"),
    (("frontend", "front-end", "front end", "full stack", "full-stack", "web developer", "ui developer"),
     "Build and deploy a responsive web app{using} with at least 3 pages, form validation, an API call and Lighthouse score above 90"),
    (("product manager", "project manager", "scrum", "business analyst"),
     "Write a product/requirements document for a real problem{using}: user stories, prioritised backlog, success metrics and a 2-sprint plan"),
    (("analyst", "bi ", "business intelligence", "analytics"),
     "End-to-end analysis: clean a public dataset with SQL/Python, build a dashboard{using} and present 3 business recommendations"),
    (("backend", "developer", "software", "java", "engineer (backend)"),
     "Build a REST service{using}, add tests, containerise it and deploy it with a CI/CD pipeline"),
    (("machine learning", "ml ", "ml engineer", "data scientist", "ai "),
     "Train and evaluate a model on a real dataset{using}, then serve predictions through a small API"),
    (("cloud", "devops", "sre"),
     "Provision infrastructure as code and deploy a containerised app through a CI/CD pipeline{using}"),
]


def capstone_for(role: str, gaps) -> str:
    using = f" using {', '.join(list(gaps)[:4])}" if gaps else ""
    r = f" {(role or '').lower()} "
    for keys, text in CAPSTONES:
        if any(k in r for k in keys):
            return text.format(using=using)
    return f"Portfolio project for {role or 'your target role'}{using}: plan, build and document it on GitHub"
