# Utah Legislature Automation

![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)

## Overview

The **Utah Legislature Automation** project employs a suite of Python scripts developed to aid Government Affairs teams in automating and enhancing the analysis and evaluation of legislative bills within the state of Utah. These tools extend beyond the mere extraction of legislative data, facilitating rapid prioritization and the discernment of potential impacts bills might impose on local jurisdictions. Through the utilization of Artificial Intelligence, the project autonomously generates impact ratings, assesses potential impacts, and offers explanations thereof. Furthermore, an implementation of a fine-tuned Large Language Model (LLM) trained on Utah Code allows for a ChatGPT like question/answer functionality when researching Utah Code. 

However, it is crucial to acknowledge that the application of AI serves the purpose of streamlining the prioritization of bills for subsequent manual review and analysis based on their projected impacts. The project is intentionally designed to supplement and complement the efforts of proficient Government Affairs teams in various municipalities, rather than substituting their expertise.

## Key Objectives
The aim of the Utah Legislature Automation project is to create a new level of operational efficiency within Government Affairs teams. While preserving the significance of human insight and judgment, these tools help to expedite the analysis and assessment of legislative bills. In doing so, the project effectively streamlines the decision-making process by identifying and prioritizing bills that warrant heightened scrutiny. It is essential to recognize that the project is designed to complement the manual review process, rather than supplant it.

## Large Language Model
The fine-tuned large language model adheres to a straightforward workflow. Initially, it retrieves the latest Utah Code and structures it in a format optimized for model embedding creation. This data is then downloaded into a designated folder named "utcode" and organized into individual files according to Title. Subsequently, the model training process ensues.

Once these procedures have concluded, the server can be initiated. Built on Flask, the server establishes an API endpoint that seamlessly integrates into various applications. The API output is a JSON response delivered through GET requests. Example response:

```
{"response":"CodeLogic AI: Utah Code Annotated § 59-12-301 and Utah Code Annotated § 59-12-405 mention the Transient Room Tax."}
```

Precision in prompts is crucial when interacting with Large Language Models. Despite having vast knowledge, AI lacks inherent wisdom. For instance, a broad query like "Where is TRT referenced?" may not yield the desired results. It is essential to be explicit and clear in your prompts, specifying details such as "transient room tax" instead of just "TRT." A more effective example would be: "Where is the Transient Room Tax referenced in the Utah Code?""

## Example Usage - Bill Analysis
python app.py bills\
python app.py --year 2023 --session S1\
python app.py impact

## Example Usage - Generative AI (LLM) trained on Utah Code
python app.py updatecode\
python app.py train\
python app.py server

The "updatecode" function will pull down the most recent version of Utah Code. This will need to be run after each legislative session after the updated code is available online. 

The "train" function will train the Large Language Model (LLM) on Utah Code. Each time you run "updatecode" you will also need to retrain in order to incorporate changes to Utah Code in the model.

The "server" function starts the API server so that it can be incorprated into your program.

## Example AI Analysis
### HB0129 2017 General Session

>The highlighted provisions have a potential impact on municipalities in Utah by defining "emergency protective services," requiring Adult Protective Services to provide such services subject to court order, providing access to the Adult Protective Services database for the Division of Occupational and Professional Licensing, clarifying that protective services are provided only on a voluntary basis, clarifying the venue for court proceedings for protective services and emergency protective services, establishing requirements and the process for a court to order emergency protective services, setting time limits for emergency protective services, allowing a court to authorize forcible entry into premises, repealing authority and procedures for court-ordered involuntary protective services, and making technical changes.

>Economic Effects:
Local businesses may be affected positively as emergency protective services could lead to increased demand for services such as home health care providers, assisted living facilities, and other services catering to vulnerable adults.
Tax revenue may be impacted if emergency protective services require additional funding from the local government. The cost of providing these services, including staff training, equipment, and facility renovations, may increase the burden on the local budget.

>Social Effects:
The provision requiring Adult Protective Services to provide emergency protective services subject to court order ensures that vulnerable adults receive necessary and timely assistance in emergency situations, improving their well-being.
The time limits for emergency protective services give vulnerable adults a clear timeframe for receiving support, preventing prolonged or unnecessary intervention.

>Legal Effects:
Granting access to the Adult Protective Services database to the Division of Occupational and Professional Licensing allows for improved coordination and communication between these entities, streamlining the process and avoiding duplication of efforts.
The provision clarifying the venue for court proceedings ensures efficient and effective legal processes for ordering protective services.
Allowing a court to authorize forcible entry into premises where vulnerable adults may be found can ensure the safety of these individuals and facilitate immediate intervention when necessary.

>Local Government Operations:
The establishment of requirements and a process for court-ordered emergency protective services provides a clear and structured framework under which local governments can operate, ensuring accountability and standardized procedures.
Repealing authority and procedures for court-ordered involuntary protective services may reduce administrative burdens on local governments, allowing them to focus on other priorities.

>Community Resources:
The provision for emergency protective services provides additional resources and support for vulnerable adults, ensuring their safety and well-being during emergencies.
However, the potential increase in demand for these services may strain existing community resources, requiring local governments to allocate additional resources to meet the needs of vulnerable adults.

>Residents' Quality of Life:
The availability of emergency protective services through court order can enhance the quality of life for vulnerable adults, addressing any immediate threats to their safety and potentially preventing further abuse or neglect.

>Alignment with Municipal Laws and Regulations:
These provisions align with existing municipal laws and regulations related to the protection and well-being of vulnerable adults, providing a clear and regulated framework for the provision of emergency protective services.

>In summary, these provisions have both positive and negative effects on Utah municipalities. While they enhance vulnerable adults' well-being and safety, they may strain local resources and require additional funding. Decision-makers should consider the potential economic, social, and legal consequences of the provisions to ensure they align with local government operations, community resources, resident well-being, and legal frameworks.

## REQUIREMENTS
*  A MySQL/MariaDB database with proper access rights. Currently, we are using Amazon AWS RDS.
*  Python 3.7+.

This system is designed to be easy to run and maintain, but you will need some basic understanding of databases, python, and server administration to get it up and running. We are running this on Ubuntu Server and use the included service file for the API, and Cron to automate the bill tasks.

## License
This project is developed under the Apache License 2.0. Refer to the LICENSE file for a comprehensive overview.

## Disclaimer
The Utah Legislature Automation project is a critical asset designed to enhance the Government Affairs team's operational efficacy. It is essential to underscore that while these tools augment the decision-making process, they are designed to complement, rather than substitute, the nuanced insight inherent in human review. The automated assessments and generated explanations are valuable adjuncts, facilitating more expedient prioritization and comprehensive understanding. This project is still under active development and refinement and may not work as expected -- it may not work at all. Once the code is stable, this disclaimer will be removed/modified.

## Author
Lance Haynie\
Government Affairs Director\
Santa Clara City

## Example GUI
![Language Model](https://raw.githubusercontent.com/sccity/utlegislature/master/img/llm_mobile.png)
![Legislative Bill Tracking](https://raw.githubusercontent.com/sccity/utlegislature/b38da668d3a266cc31a1f4bf56d876c763575e9d/img/utle.png)