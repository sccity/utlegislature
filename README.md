# Utah Legislature Automation

![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)

## Overview

The **Utah Legislature Automation** project employs a suite of Python scripts developed to aid Government Affairs teams in automating and enhancing the analysis and evaluation of legislative bills within the state of Utah. These tools extend beyond the mere extraction of legislative data, facilitating rapid prioritization and the discernment of potential impacts bills might impose on local jurisdictions. Through the utilization of Artificial Intelligence, the project autonomously generates impact ratings, assesses potential impacts, and offers explanations thereof. Furthermore, an implementation of a fine-tuned Large Language Model (LLM) trained on Utah Code allows for a ChatGPT like question/answer functionality when researching Utah Code. 

However, it is crucial to acknowledge that the application of AI serves the purpose of streamlining the prioritization of bills for subsequent manual review and analysis based on their projected impacts. The project is intentionally designed to supplement and complement the efforts of proficient Government Affairs teams in various municipalities, rather than substituting their expertise.

## Key Objectives
The aim of the Utah Legislature Automation project is to create a new level of operational efficiency within Government Affairs teams. While preserving the significance of human insight and judgment, these tools help to expedite the analysis and assessment of legislative bills. In doing so, the project effectively streamlines the decision-making process by identifying and prioritizing bills that warrant heightened scrutiny. It is essential to recognize that the project is designed to complement the manual review process, rather than supplant it.

## License
This project is developed under the Apache License 2.0. Refer to the LICENSE file for a comprehensive overview.

## Example Usage - Bill Analysis
python app.py bills\
python app.py --year 2023 --session S1\
python app.py impact

## Example Usage - Generative AI (LLM) trained on Utah Code
python app.py updatecode\
python app.py train\
python app.py server\

The "updatecode" function will pull down the most recent version of Utah Code. This will need to be run after each legislative session after the updated code is available online. 

The "train" function will train the Large Language Model (LLM) on Utah Code. Each time you run "updatecode" you will also need to retrain in order to incorporate changes to Utah Code in the model.

The "server" function starts the API server so that it can be incorprated into your program.

## Author
Lance Haynie\
Government Affairs Director\
Santa Clara City

## Disclaimer
The Utah Legislature Automation project is a critical asset designed to enhance the Government Affairs team's operational efficacy. It is essential to underscore that while these tools augment the decision-making process, they are designed to complement, rather than substitute, the nuanced insight inherent in human review. The automated assessments and generated explanations are valuable adjuncts, facilitating more expedient prioritization and comprehensive understanding. This project is still under active development and refinement and may not work as expected -- it may not work at all. Once the code is stable, this disclaimer will be removed/modified.

## Example GUI
![Legislative Bill Tracking](https://raw.githubusercontent.com/sccity/utlegislature/b38da668d3a266cc31a1f4bf56d876c763575e9d/img/utle.png)