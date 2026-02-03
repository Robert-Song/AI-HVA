# AI-HVA
AI-Pipeline for Hardware Vulnerability Analysis (Sandia National Lab)

## Project Overview

This project is a design document for an automated tool to transform electrical schematics into standardized safety analysis models. The primary goal is to drastically improve the speed of safety analysis for **high-consequence hardware** (like nuclear systems and satellites), which currently requires weeks of manual extraction from schematics and datasheets.

The pipeline automates this process to provide assurances about cyber-physical systems quickly and efficiently.

## Design Highlights and Key Features

The system is built on a robust, security-conscious architecture with key decisions made to ensure accuracy, scalability, and data privacy.

| Feature Area           | Decision                                                                  | Rationale                                                                                                                                                                                                                                                                               |
| :--------------------- | :------------------------------------------------------------------------ | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Architecture**       | **Client-Server Model** with separated Internet-facing server.            | Improves security and allows independent scaling by isolating the LLM subsystem and external resource access.                                                                                                                                                                           |
| **LLM Reasoning**      | **Hybrid RAG and Verification Loop**.               | Uses a standard Retrieval-Augmented Generation (RAG) pipeline for initial inference, followed by a dedicated verification step that strictly validates generated claims against the provided datasheet text to ensure auditability and prevent hallucination in safety-critical output. |
| **Analysis Model**     | **User-Selected Component Abstraction**.                       | Allows the expert user to select/deselect specific components for inclusion in the abstraction layer, ensuring the generated model matches the specific safety context of the analysis (e.g., STPA).                                                                                    |
| **Data Privacy**       | **Local, Lightweight Vector Store**.                           | Keeps all sensitive schematic data and vector embeddings contained within the user's local machine or secure environment, as storing high-consequence hardware data in the public cloud is unacceptable.                                                                                |
| **Deployment**         | **Docker Containers**.                                         | Packages the entire pipeline (Ingest, Vector DB, Analysis) into three containers for an isolated, reproducible, and easily deployable environment, satisfying the client's requirement.                                                                                                 |
| **User Interaction**   | **Dual Interface (GUI and CLI)**.                              | Develops a core processing engine that exposes functionality to both a GUI for average users (file upload, visualization) and a CLI for power users (scripting, automation, headless operation).                                                                                        |
| **Output Consistency** | **Hybrid Prompting and Dedicated Repair Pipeline**. | Uses strict system prompts for the main model, and a secondary, small specialized LLM to fix any syntax errors, guaranteeing the output is highly compliant with the STPA JSON schema.                                                                                                  |

## Core Component Interactions

The pipeline consists of the following major components:

1.  **Frontend Client (React):** User interface for file upload, analysis request submission, and displaying human-readable results.
2.  **Server (Python Backend):** Handles internal processing, parses/validates user files, manages the vector database for RAG, and coordinates with the Internet-facing Server.
3.  **Internet-facing Server:** Acts as a controlled edge layer, downloading missing datasheets from external resources, running the RAG query workflow, and communicating with the LLM Subsystem.
4.  **RAG + LLM Subsystem:** Generates the structured safety analysis output. It uses a **Chunking and RAG Strategy** to efficiently retrieve only the most relevant sections of large datasheets, avoiding token limits and high costs.

## Design Details (Main Modules)

| Module                      | Functionality                                                                                                                                                                                      |
| :-------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **FileHandler**             | Takes KiCad file path, extracts content, and sends to Parser. Also records training data for MLTrainer.                                                                                            |
| **Parser**                  | Takes KiCad content, deserializes it into a `KiCadObject` (hierarchical data structure).                                                                                                           |
| **InfoCompressor**          | Takes the `KiCadObject` and returns a condensed, readable string for the LLM.                                                                                                                      |
| **MLResponse**              | Requests/generates the analysis response using its up-to-date model, aiming for valid JSON output following STPA standards.                                                                        |
| **STPACheck / JSONCheck**   | Validation layers that check the MLResponse output against STPA standards and valid JSON format, sending invalid results back to `MLResponse` for correction (part of the Output Validation Loop). |
| **MLTrainer**               | Collects data and runs the process to train or update the ML model.                                                                                                                                |
| **GUIWrapper / CLIWrapper** | Interfaces the core processing logic with the respective user interaction methods.                                                                                                                 |

