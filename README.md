# ISEC - Information Systems II (SI2) - Figueira da Foz Port Data Mart (2025/2026)

### Context

This repository contains the project materials developed for the practical assignment of the Information Systems II (SI2) course unit, part of the Computer Engineering degree at the Coimbra Institute of Engineering (ISEC), during the 2025/2026 academic year.

### Project Goal

The primary objective was to create a decision support system backed by a Data Mart to analyze commercial ship voyages concluding at the Maritime Port of Figueira da Foz. The project aimed to consolidate fragmented data from an operational ERP and historical files to provide strategic indicators and actionable insights through Microsoft Power BI dashboards.

### Key Aspects Covered

*   **Data Integration & ETL:** Development of a robust Python script to extract, transform, and load (ETL) data from heterogeneous sources (an operational MySQL database, a CSV file, and Mockaroo synthetic data) into a SQL Server Staging Area, and finally into the Data Mart.
*   **Dimensional Modeling:** Design and implementation of a Star Schema comprising a central Fact Table (Viagens) and multiple Dimensions (Tempo, Barco, Condutor, LocalizacaoOrigem, EmpresaBarco, TipoViagem) at a specific grain (one record per completed voyage).
*   **Business Intelligence & KPIs:** Creation of interactive Power BI dashboards and a Visual Studio Analysis Services cube to monitor strategic KPIs, such as revenue from taxes by origin country, trip duration analysis, fleet/resource management, and financial analysis by voyage type.
*   **Storage Capacity Projection:** Detailed estimation and mathematical calculation of the Data Mart's physical storage requirements and expected data growth over a 5-year horizon.

### Tools and Languages Used

*   **Databases:** SQL Server, MySQL
*   **Languages:** Python, SQL
*   **Visualization & BI:** Microsoft Power BI, Visual Studio Analysis Services
*   **Data Generation:** Mockaroo

### Repository Contents

| File / Folder | Description |
| :--- | :--- |
| `Source/` | Contains the Python ETL scripts, SQL scripts for database creation/staging, and the Power BI (`.pbix`) dashboard files. |
| `Enunciado_SI2_Trabalho_Pratico.pdf` | The original assignment brief detailing the business rules and constraints. |
| `Relatorio_SI2_TP_Grupo.pdf` | The detailed project report outlining the architecture, ETL logic, dimensional modeling, and 5-year storage projections. |

### Authors

*   Diogo Silva
*   André Tavares
