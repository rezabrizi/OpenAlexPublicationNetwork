# OpenAlex Citation Network

This library allows you to easily extract and analyze various citation networks from the OpenAlex repository. The library enables the creation of citation graphs for research studies focused on publication networks. OpenAlex contains more than 250 million publications, and this tool helps build structured citation graphs where a directed edge from one publication to another represents a citation.

A key feature of this library is **direct cascade extraction using breadth-first search (BFS)**. For example, if paper A cites papers B and C, paper B cites papers C and D, and paper C cites paper E, this library extracts papers (A, B, C, D, and E) in a **level-by-level order**. This approach works by selecting one or more publications as **root nodes** and expanding citations level by level.

## Features

- **General Research Network Extraction**

  - **Search**: Query publications by title, abstract, or full text.
  - **Filter**: Use OpenAlex filters ([OpenAlex Filters](https://docs.openalex.org/api-entities/works/filter-works)) to refine attributes in the work object (JSON).
  - **Sort**: Order search results using various sorting options ([OpenAlex Sort](https://docs.openalex.org/how-to-use-the-api/get-lists-of-entities/sort-entity-lists)).

- **Cascade Citation Network Extraction**
  - Select one or more publications as **root nodes**.
  - Expand citations using **BFS** to construct a **cascade-like citation tree**.
- **Data Profiling and Error Handling**
  - Use the built-in **profiler** to analyze dataset accuracy and view any errors during extraction.
- **Graph Construction with igraph**

  - Build a **citation network as an igraph Graph object**.
  - Metadata includes: `title`, `id`, `doi`, `publication_year`, `abstract_inverted_index`, and other OpenAlex attributes.

- **Save and Load Graphs**
  - Export citation networks as **CSV** to avoid repeated downloads.
  - Reload saved **CSV files** to recreate igraph objects.

## Installation

This project uses **Poetry** for dependency management. To install, run:

```bash
pip install poetry
poetry install
```

## Usage

### 1. Creating a Citation Network

```python
from citation_network.network import createCitationGraph
from citation_network.crawler import EntitiesCrawler

# Initialize crawler
crawler = EntitiesCrawler(email="your-email@example.com")

# Retrieve entities (Example: Filter by topic and year)
entities = crawler.getEntities(filter={"primary_topic": "machine learning", "publication_year": "2020"}, maxEntities=5000)

# Build the citation graph
graph = createCitationGraph(entities)

# Save the graph
graph.write_csv("citation_network.csv")
```

### 2. Loading a Citation Network from CSV

```python
from citation_network.utils import create_citation_graph_from_csv

graph = create_citation_graph_from_csv("citation_network.csv")
print(graph.summary())
```

### 3. Extracting a Citation Cascade using BFS

```python
# Perform BFS on citations up to a specified depth
bfs_results = crawler.citationBFS(root=["W1234567890"], maxLevels=5, maxNodes=10000)
```

## Jupyter Notebook

For detailed examples and interactive exploration, refer to **notebook.ipynb**.

## Logging

The library includes built-in logging, which can be configured at different levels:

```python
import logging
from citation_network.logging_setup import setup_logging

setup_logging(logging.DEBUG)  # Set logging level to DEBUG
```

This ensures detailed insights into extraction processes and debugging capabilities.

---

This library provides an efficient way to extract and analyze publication networks, making it valuable for researchers in **citation analysis, network science, and information diffusion modeling**.

## Citation

If you use this library, please cite:

Priem, J., Piwowar, H., & Orr, R. (2022). OpenAlex: A fully-open index of scholarly works, authors, venues, institutions, and concepts. ArXiv. [https://arxiv.org/abs/2205.01833](https://arxiv.org/abs/2205.01833)
