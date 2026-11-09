# Career retrieval audit (E37)

2026-11-09T16:47:37.745615+00:00

## Strict P@5 by configuration

| Set | n | vector | vector+ce | ce+skill(d6) | ce+skill(d3) | ce+skill(d0) | hybrid+ce+skill(d3) |
|---|---|---|---|---|---|---|---|
| tuning_24 | 24 | 0.767 | 0.858 | 0.933 | 0.892 | 0.858 | 0.892 |
| heldout_30 (E36, audited) | 30 | 0.727 | 0.713 | 0.773 | 0.753 | 0.707 | 0.78 |
| heldout_v2_20 (frozen, final) | 20 | 0.61 | 0.64 | 0.69 | 0.67 | 0.65 | 0.6 |

## By query type

**tuning_24**

| Type | n | vector | vector+ce | ce+skill(d6) | ce+skill(d3) | ce+skill(d0) | hybrid+ce+skill(d3) |
|---|---|---|---|---|---|---|---|
| interest | 17 | 0.718 | 0.835 | 0.906 | 0.859 | 0.847 | 0.847 |
| skill | 7 | 0.886 | 0.914 | 1.0 | 0.971 | 0.886 | 1.0 |

**heldout_30 (E36, audited)**

| Type | n | vector | vector+ce | ce+skill(d6) | ce+skill(d3) | ce+skill(d0) | hybrid+ce+skill(d3) |
|---|---|---|---|---|---|---|---|
| interest | 17 | 0.788 | 0.765 | 0.8 | 0.788 | 0.765 | 0.824 |
| skill | 7 | 0.714 | 0.657 | 0.829 | 0.771 | 0.657 | 0.771 |
| title | 6 | 0.567 | 0.633 | 0.633 | 0.633 | 0.6 | 0.667 |

**heldout_v2_20 (frozen, final)**

| Type | n | vector | vector+ce | ce+skill(d6) | ce+skill(d3) | ce+skill(d0) | hybrid+ce+skill(d3) |
|---|---|---|---|---|---|---|---|
| interest | 5 | 0.4 | 0.4 | 0.52 | 0.48 | 0.4 | 0.24 |
| skill | 5 | 0.8 | 0.8 | 0.84 | 0.8 | 0.8 | 0.84 |
| title | 5 | 0.8 | 0.88 | 0.92 | 0.92 | 0.88 | 0.84 |
| transition | 5 | 0.44 | 0.48 | 0.48 | 0.48 | 0.52 | 0.48 |

## Audit of the 30 E36 held-out queries (config ce+skill(d3))

Diagnoses: ok × 19, ranking × 8, source_data / mixed × 3

| Query | Type | P@5 | Diagnosis | Top-5 (✓ relevant) |
|---|---|---|---|---|
| sports performance data analyst | title | 0.0 | ranking (relevant records in the pool, not in the top 5) | ✗ Basketball Data Analyst (Machine Learning and AI); ✗ Sports Data Operator, Monitoring (Part-Time) (Technology and Business Operations); ✗ Sports Data Operator, Live Data Entry (Technology and Business Operations); ✗ Game Data Analyst, Monetization (Data Engineering); ✗ Business Performance Analyst (Data Engineering) |
| embedded systems and IoT firmware with C | skill | 0.0 | source_data / mixed (few relevant records exist) | ✗ Cloud Architect (Data Engineering); ✗ Cloud IoT Architect (Machine Learning and AI); ✗ SYSTEMS ARCHITECT (Project and Business Management); ✗ IOT Architect (Machine Learning and AI); ✗ Principal IoT Identity and Access Technologist (Project and Business Management) |
| I want to manage agile software projects as a scrum master | interest | 0.2 | ranking (relevant records in the pool, not in the top 5) | ✓ Scrum Master (Los Angeles) (Project and Business Management); ✗ Business Analyst 2571 (Data Analysis and BI); ✗ Project Manager Big Data Analytics (Data Engineering); ✗ Analyst, Information Management (Software and Web Development); ✗ Manager of Supply Chain & Merchandising Applications (Software and Web Development) |
| writing Python scripts to automate repetitive office work | interest | 0.2 | source_data / mixed (few relevant records exist) | ✓ Python Integration Engineer (Data Engineering); ✗ OFFICE ASSISTANT (TEMP) (Operations and Administration); ✗ Office Specialist II (Operations and Administration); ✗ MANAGER, OFFICE (Operations and Administration); ✗ Administrative Intern (Operations and Administration) |
| quantitative analyst building trading models | title | 0.4 | source_data / mixed (few relevant records exist) | ✓ Quantitative researcher (Machine Learning and AI); ✓ Quantitative Analyst (Machine Learning and AI); ✗ Business Analyst (Data Analysis and BI); ✗ Quantitative Business Analyst, Trust and Safety, YouTube (Data Analysis and BI); ✗ Corporate Strategy Business Analyst (Data Analysis and BI) |
| career for someone who knows Python, SQL and Excel | skill | 0.6 | ranking (relevant records in the pool, not in the top 5) | ✓ Business Analyst (Data Engineering); ✓ Python Integration Engineer (Data Engineering); ✗ Junior Data Scientist (Machine Learning and AI); ✗ Python Developer - Data Analysis (Software and Web Development); ✓ Data Engineer - Digital Wealth (Data Engineering) |
| Java backend engineer building APIs | title | 0.6 | ranking (relevant records in the pool, not in the top 5) | ✓ Java Developer (Software and Web Development); ✓ Software Engineer (Software and Web Development); ✗ Java Full-Stack Engineer (Cloud and DevOps); ✗ Backend Architect (Cloud and DevOps); ✓ Principal Implementation Engineer, Java Developer, Remote (Services) (Software and Web Development) |
| fraud detection and credit risk analytics in banking | interest | 0.6 | ranking (relevant records in the pool, not in the top 5) | ✓ Employee Fraud Detection Risk Manager - Monitoring and Analytics (Data Analysis and BI); ✗ Fraud Analyst 4 (Technology and Business Operations); ✓ Card Operations Fraud Analyst (Machine Learning and AI); ✓ Fraud Decision Scientist (Machine Learning and AI); ✗ Investigator - Regional Investigations - Global Security & Investigations (Project and Business Management) |
| product manager for a SaaS platform | interest | 0.6 | ranking (relevant records in the pool, not in the top 5) | ✓ Inside Sales and Customer Growth Manager, Google Cloud (Project and Business Management); ✓ Global Account Manager - East (Project and Business Management); ✗ Product Support Representative (Machine Learning and AI); ✓ Product Manager I (Product, UX and Design); ✗ Product Manager, Voice Experiences (Machine Learning and AI) |
| personalised recommendation engines for streaming platforms | interest | 0.6 | ranking (relevant records in the pool, not in the top 5) | ✓ Expert Data Scientist (Machine Learning and AI); ✗ Sr. Staff Architect(Events & Streaming) (Data Engineering); ✗ Spark Data Engineer (Data Engineering); ✓ Product Manager, Voice Experiences (Machine Learning and AI); ✓ Big Data Delivery Engineer (REMOTE) - Professional Services (Machine Learning and AI) |
| MLOps engineer deploying models to production | interest | 0.6 | ranking (relevant records in the pool, not in the top 5) | ✓ Cloud Engineer (Cloud and DevOps); ✓ DPS - IT - Jr Systems Engineer (Cloud and DevOps); ✓ Cloud / AWS Architect (Cloud and DevOps); ✗ Software Engineer - Full Stack (Cloud and DevOps); ✗ Forward Deployed Engineer (Design, Engineering and Other Technical) |
| master data management and data quality governance | skill | 0.8 | ok | ✓ Data Delivery - Data Governance and Quality - Manager (Data Architecture and Governance); ✓ Master Data Management (MDM) Manager (Data Analysis and BI); ✓ Manager, Master Data Management (Data Engineering); ✓ Manager I, Master Data Office (MDO) (Data Analysis and BI); ✗ Sr. Manager Data Governance (AMGA627) (Cybersecurity and Networking) |
| digital marketing analyst tracking campaign performance | interest | 0.8 | ok | ✓ Digital Marketing Analyst (Data Analysis and BI); ✓ Analyst, Media Operations (Marketing, Sales and Customer Operations); ✓ Digital Media Analyst (Data Analysis and BI); ✓ Manager, Business Intelligence & Analytics (Data Analysis and BI); ✗ Marketing Data Analyst (Data Science and Research) |
| Power BI developer creating DAX reports | interest | 0.8 | ok | ✓ REPORTING ANALYST - REDMOND, WA (Data Analysis and BI); ✗ Consultant - Analytics (Microsoft Power BI and Data Science) (Machine Learning and AI); ✓ Business Intelligence Analyst (Data Analysis and BI); ✓ Associate HR Business Intelligence Analyst (Data Analysis and BI); ✓ Financial Business Analyst (PowerApps) (Data Analysis and BI) |
| ethical hacker doing vulnerability assessments | title | 0.8 | ok | ✓ Cyber Security Analyst (Cybersecurity and Networking); ✓ Cyber Security Analyst (Cybersecurity and Networking); ✗ Investigations Analyst, Ethical ML, Trust and Safety (Technology and Business Operations); ✓ Information Security Analyst (Cybersecurity and Networking); ✓ Security Analyst (Cybersecurity and Networking) |
| I want to analyse sales data and build KPI dashboards for managers | interest | 1.0 | ok | ✓ Analytics Manager (Data Analysis and BI); ✓ Smashbox - Manager, Consumer Engagement, Insights and Analytics (Data Analysis and BI); ✓ Manager, Data and Audience Activation (Data Analysis and BI); ✓ Sr. Manager, Business Data Analytics (Data Analysis and BI); ✓ MANAGER-MARKETING ANALYTICS (Data Analysis and BI) |
| I enjoy training deep learning models with PyTorch | interest | 1.0 | ok | ✓ Deep Learning Engineer (Satellite Imaging) (Machine Learning and AI); ✓ Data Scientist (Deep Learning) (Machine Learning and AI); ✓ Research Staff Member, Distributed Deep Learning Platform (Machine Learning and AI); ✓ Machine Learning Engineer / AD (Machine Learning and AI); ✓ Computer Vision Engineer (Deep Learning/Satellite Imaging) (Machine Learning and AI) |
| roles building ETL pipelines in the cloud with Spark | skill | 1.0 | ok | ✓ Software Development Engineer, Big Data (Data Engineering); ✓ Data Engineer (Spark, Docker, AWS) (Data Engineering); ✓ Enterprise ETL Engineer (Data Engineering); ✓ Data Engineer - AWS (Data Engineering); ✓ Cloud Architect (Data Engineering) |
| I like automating infrastructure with Terraform and Kubernetes | interest | 1.0 | ok | ✓ Solutions Architect, DevOps, Google Cloud (Cloud and DevOps); ✓ Cloud Engineer (Cloud and DevOps); ✓ Software Architect (Cloud and DevOps); ✓ AWS Cloud Infrastructure Architect (Cloud and DevOps); ✓ Cloud Developer Intern (Cloud and DevOps) |
| I want to investigate security incidents and monitor threats in a SOC | interest | 1.0 | ok | ✓ SOC Analyst / Security Operations Administrator (Cybersecurity and Networking); ✓ Security Analyst (Cybersecurity and Networking); ✓ Information Security Analyst (Cybersecurity and Networking); ✓ Information Security Analyst I (Cybersecurity and Networking); ✓ Security Analyst (Cybersecurity and Networking) |
| full stack web developer with JavaScript and React | skill | 1.0 | ok | ✓ Full Stack JavaScript developer (React, Node) (Software and Web Development); ✓ Full Stack JavaScript Developer (Software and Web Development); ✓ Full Stack .NET Developer (Software and Web Development); ✓ Entry level Full Stack Web Developer (Software and Web Development); ✓ Full Stack Engineer (Software and Web Development) |
| chatbots and generative AI with large language models | skill | 1.0 | ok | ✓ Fall AI Lab Internship (Machine Learning and AI); ✓ Artificial Intelligence (AI) Engineer, gRED Early Clinical Development (Machine Learning and AI); ✓ Los Angeles - Software Engineer, Machine Learning (Machine Learning and AI); ✓ Product Manager, Voice Experiences (Machine Learning and AI); ✓ Artificial Intelligence Senior Manager (Machine Learning and AI) |
| designing user experience and wireframes for mobile apps | interest | 1.0 | ok | ✓ User Experience Designer (Software and Web Development); ✓ Software Developer (Software and Web Development); ✓ UX Designer (Software and Web Development); ✓ User Experience Researcher (Product, UX and Design); ✓ User Experience Engineer (Software and Web Development) |
| research scientist running statistical experiments | title | 1.0 | ok | ✓ Research Scientist (Data Science and Research); ✓ STOPS RESEARCH SCIENTIST 1 (Data Science and Research); ✓ DATA SCIENTIST (Data Science and Research); ✓ Data Scientist (Data Science and Research); ✓ Data Scientist (Data Science and Research) |
| help desk role solving employees' laptop and network issues | interest | 1.0 | ok | ✓ Remote Help Desk Tech (IT Support and Systems); ✓ IT Desktop/Help Desk Support - Technical Craft Specialist A (IT Support and Systems); ✓ IT Helpdesk (IT Support and Systems); ✓ Systems Administrator (Cybersecurity and Networking); ✓ Corporate IT Systems Administrator I (Cybersecurity and Networking) |
| image recognition and object detection engineer | interest | 1.0 | ok | ✓ Computer Vision Engineer (Deep Learning/Satellite Imaging) (Machine Learning and AI); ✓ Deep Learning Engineer (Satellite Imaging) (Machine Learning and AI); ✓ Scientist: Computer Vision & Machine Learning (Machine Learning and AI); ✓ Software Engineer, Machine Learning and Graphics (Machine Learning and AI); ✓ Software Engineer, Machine Learning (Machine Learning and AI) |
| Linux system administrator managing servers | title | 1.0 | ok | ✓ Linux Systems Administrator (Cybersecurity and Networking); ✓ System Administrator - Temporary (Cybersecurity and Networking); ✓ Systems Administrator (Linux & Windows) (Cybersecurity and Networking); ✓ Linux Administrator (Cloud and DevOps); ✓ Operations Systems Administrator (Cybersecurity and Networking) |
| Azure cloud solutions architect | skill | 1.0 | ok | ✓ Azure Cloud Architect Associate - Consumer Markets (Cloud and DevOps); ✓ Cloud Infrastructure Architect (Cloud and DevOps); ✓ Senior Cloud Solutions Architect (Cloud and DevOps); ✓ Associate Director, Cloud Solutions Architect (Cloud and DevOps); ✓ Cloud Solution Architect, Director (Cloud and DevOps) |
| real-time data streaming engineer using Kafka | interest | 1.0 | ok | ✓ Data Engineer (Data Engineering); ✓ Sr. Staff Architect(Events & Streaming) (Data Engineering); ✓ Big Data Engineer (Data Engineering); ✓ Software Engineer - Big Data/Spark/Kafka (Data Engineering); ✓ Spark Data Engineer (Data Engineering) |
| business analyst gathering requirements between IT and stakeholders | interest | 1.0 | ok | ✓ Business Analyst (Data Analysis and BI); ✓ Business Analyst (Data Analysis and BI); ✓ Business Analyst (Data Analysis and BI); ✓ Business Analyst (Data Analysis and BI); ✓ business analyst (Data Analysis and BI) |
