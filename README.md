# Mock Trial AI

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
This project currently offers three core functionalities designed to cover the lifecycle of trial preparation. The Case Analysis module allows users to conduct specialized reviews of their materials to extract and refine the Prosecution or Defense Theory within a specific case. The Cross-Examination Simulator provides a space for users to practice questioning against the opposition's witnesses, who respond dynamically based on the provided facts. Finally, the Objection Practice module enables users to identify objections based on witness examination questions in a variety of chosen formats.

## Usage Guide
The application is currently hosted at mock-trial-ai.streamlit.app. To use the model, users first select their desired tool from the interface and then upload or paste the raw text of their case packet. Depending on the selected mode, you will either input the specific type of case analysis required or provide the name of a witness and select the type of examination you wish to perform. If the app is not running due to resource limits, please reach out to me at vihaan.ph@gmail.com and I will manually restore the instance.

## Technical Challenges & Limitations
The current iteration of the Objection Practice has a significant limitation in pure prompt engineering, as the AI frequently fails to recognize objectionable content. For instance, the model occasionally generates leading questions during direct examinations but incorrectly classifies them as non-objectionable. This occurs because these base models have not been trained to recognize objections and don't have the proper weights to recognize them.

Case Analysis occasionally hallucinates. This occurs because standard OpenAI attention mechanisms are not natively tuned to prioritize the rigid hierarchical structure of legal documents over general language patterns. Consequently, the AI often struggles with "fact-blurring," where it confuses procedural meta-facts with actual case evidence, a problem that scales with the complexity and lack of formal structure in the input case packets.

## The Road to V2: Future Work
To resolve these hurdles, the project is moving toward a version that utilizes domain-specific fine-tuning on curated case packet data to establish more appropriate attention weights for legal logic. I am currently developing Mock Trial AI V2, which aims to move beyond the "intelligence ceiling" of simple prompting to create a model that understands the nuanced boundaries of legal testimony. You can follow the development of this second version on my GitHub repository and my Hugging Face account under the username hobbesthecomputerscientist.

## Real-World Impact
The platform is currently being integrated into the official mock trial curriculum in collaboration with student leadership at San Francisco University High School. By transitioning from static case packets to an interactive AI-driven environment, the project aims to standardize witness preparation and evidentiary training across the team. This pilot phase focuses on using the simulation to reduce the cognitive load of rapid objection retrieval and to stress-test Prosecution and Defense theories against a dynamic, fact-consistent adversary before formal competitions.

## Contributing
Contributions are welcome! If you have a specific "witness prompt" or legal logic improvement, please open an issue or submit a pull request.

## License
Distributed under the MIT License. See LICENSE for more information.
