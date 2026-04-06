# Mock Trial AI V1

## Table of Contents
* [Project Overview](#project-overview)
* [Features](#features)
* [Usage Guide](#usage-guide)
* [Technical Challenges & Limitations](#technical-challenges--limitations)
* [The Road to V2: Future Work](#the-road-to-v2-future-work)
* [Real-World Impact](#real-world-impact)
* [Contributing](#contributing)
* [License](#license)

## Project Overview 
Mock Trial AI is a specialized legal simulation tool powered by OpenAI's API, designed to assist mock trial competitors by providing a sandbox for witness testimony, objection detection, and strategic case theory development. By leveraging advanced prompt engineering, the system attempts to bridge the gap between static case packets and dynamic trial practice, allowing students to interact with evidence in a more conversational and intuitive environment.

## Features 
This project offers three core functionalities:
* **Case Analysis:** Specialized reviews to extract and refine Prosecution or Defense Theory.
* **Cross-Examination Simulator:** Practice questioning against dynamic, fact-consistent witnesses.
* **Objection Practice:** Identify evidentiary objections in witness examination formats.

## Usage Guide
The application is currently hosted at `mock-trial-ai.streamlit.app`. Users select a tool and upload or paste the raw text of their case packet. Input the specific analysis required or provide a witness name to begin a simulation. 
*Note: If the app is inactive due to resource limits, contact vihaan.ph@gmail.com for a manual restore.*

## Technical Challenges & Limitations
The primary limitation of V1 was the **"Black Box"** nature of the OpenAI API. Pure prompt engineering frequently failed to recognize nuanced objections (e.g., allowing leading questions on direct). Standard attention mechanisms struggled with the rigid hierarchical structure of legal documents, leading to "fact-blurring" where the AI confused procedural meta-facts with actual case evidence.

## The Road to V2: Future Work
To overcome the "intelligence ceiling" of simple prompting, the project is moving toward domain-specific fine-tuning. V2 aims to establish appropriate attention weights for legal logic by training on curated case packets. Follow development on GitHub and Hugging Face (@hobbesthecomputerscientist).

## Real-World Impact
Integrated into the official mock trial curriculum at San Francisco University High School, this pilot phase focuses on reducing the cognitive load of rapid objection retrieval, finding ideas for case theories, and stress-testing case theories against a dynamic witness.

## License
Distributed under the MIT License.
