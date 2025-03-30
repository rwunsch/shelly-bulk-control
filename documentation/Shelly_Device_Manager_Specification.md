# Shelly BULK operations tool

Enterprise-Grade Shelly Device Management Tool Specification
============================================================

Overview
--------

This document describes a **Python-based enterprise-grade tool** for discovering, configuring, and bulk-managing **Shelly IoT devices** across local networks or specified VLANs. Shelly devices are WiFi-enabled smart devices (relays, sensors, switches, etc.) that support local control via open protocols (HTTP, MQTT, CoAP) and advertise themselves using **mDNS/ DNS-SD** for easy discovery​

[docs.simpleiot.org](https://docs.simpleiot.org/docs/user/shelly.html#:~:text=Shelly%20sells%20a%20number%20of,be%20discovered%20on%20the%20network)

​

[kb.shelly.cloud](https://kb.shelly.cloud/knowledge-base/discovering-shelly-devices-via-mdns#:~:text=Why%20does%20this%20matter%20for,particularly%20important%20for%20Shelly%20devices)

. The tool will streamline management of large Shelly deployments by providing multiple interfaces (CLI, REST API, and Web GUI) and robust features for grouping and bulk configuration. It is designed with **enterprise use** in mind – meaning it must be **scalable, modular, and extensible**, with strong logging and the ability to run reliably in Docker containers for easy deployment.

The goal is to create a comprehensive management system that can integrate into various workflows. Whether an administrator prefers command-line scripting, RESTful automation, or a user-friendly web dashboard, this tool will cater to all. **Integration** with other tools and scripts is a priority (via the CLI and API), and all state and configuration data will be stored in human-readable formats (YAML) for transparency and easy version control. By leveraging modern Python frameworks and following best practices, the system will remain maintainable and ready for future enhancements like authentication or real-time updates.
Core Features
-------------

The following core features and capabilities are planned for the Shelly management tool:

1. **Device Discovery:**
   
   * **Active and Passive Scanning:** The tool will actively discover Shelly devices using known protocols (mDNS, CoAP, and optionally SSDP) and also passively listen for device announcements. Shelly devices announce themselves via **mDNS** (Multicast DNS) with a service type `_shelly._tcp.local.` that includes device details like IP, model, and firmware in TXT records​
     [kb.shelly.cloud](https://kb.shelly.cloud/knowledge-base/discovering-shelly-devices-via-mdns#:~:text=Why%20does%20this%20matter%20for,particularly%20important%20for%20Shelly%20devices)
     ​
     [kb.shelly.cloud](https://kb.shelly.cloud/knowledge-base/discovering-shelly-devices-via-mdns#:~:text=)
     . They also broadcast on a CoAP multicast address for discovery​
     [github.com](https://github.com/StyraHem/ShellyForHASS/blob/master/troubleshooting.md#:~:text=The%20plugin%20trying%20to%20discover,mDns%20messages%20on%20the%20network)
     . The tool will use these mechanisms to find devices in real-time.
   
   * **Multi-Protocol Support:** It will leverage libraries like `python-zeroconf` for mDNS discovery (to find `_shelly._tcp.local` services) and possibly a CoAP client (such as `aiocoap`) or low-level UDP listener for CoAP announcements. SSDP (UPnP discovery) can be optionally implemented to send search queries, though Shelly primarily uses mDNS​
     [github.com](https://github.com/Domi04151309/HomeApp/issues/27#:~:text=,browse%22%20to)
     .
   
   * **Subnet/VLAN Scoping:** Administrators can specify which subnets or VLAN interfaces to scan. This prevents unnecessary network noise and focuses discovery on intended network segments. For example, one might limit discovery to an IoT VLAN (e.g. `192.168.10.0/24`) to find devices only on that segment. The tool will allow configuring target IP ranges or network interfaces for scanning.
   
   * **Fallback IP Scan:** For devices that do not announce themselves (or if mDNS is blocked across VLANs), the tool can perform an IP range scan. This might involve pinging or sending HTTP requests on common Shelly ports (like port 80) to identify Shelly devices by their response or known endpoints. This **active probing** ensures even "silent" devices can be discovered (at the cost of more network traffic).

2. **Device Classification & Capability Mapping:**
   
   * **Identify Device Type and Firmware:** Once a device is discovered, the tool will query it to determine its model and capabilities. Shelly devices provide identification info via mDNS TXT records (e.g., an `app` field for model and `ver` for firmware​
     [kb.shelly.cloud](https://kb.shelly.cloud/knowledge-base/discovering-shelly-devices-via-mdns#:~:text=)
     ) or through their HTTP API. Using this information, the tool classifies the device (e.g., Shelly 1PM, Shelly 2.5, Shelly Plug, Shelly Pro 4PM, etc.).
   
   * **Capability Profiling:** Based on the device type (model and generation), the tool loads a profile of its capabilities and configurable parameters. For example, a **Shelly 2.5** has two relay outputs and power monitoring, whereas a **Shelly H&T** (humidity & temperature sensor) has battery status and sensor thresholds. The software will maintain a catalog of device models and their features (either hard-coded in a data file or retrieved from Shelly documentation) to know what settings and commands each device supports.
   
   * **Device Capabilities System:** The tool implements a robust capabilities system that automatically discovers and catalogs the exact capabilities of different Shelly devices. This system scans devices using their APIs to determine supported parameters, endpoints, and features, creating detailed capability profiles stored as YAML files. Administrators can use the capabilities system to check parameter support across different device types or scan their network to automatically generate capability definitions for all discovered devices. See the [Device Capabilities](Device_Capabilities.md) documentation for more details.
   
   * **Fetch Current State and Settings:** The tool will retrieve each device's current configuration and state. Shelly devices have an **HTTP API** (and newer models have an RPC API) that can return status and settings (e.g., via endpoints like `/status` or `/settings` for Gen1 devices, or RPC calls for Gen2 devices). Using these, the tool can map all relevant parameters (such as WiFi settings, MQTT configuration, timers, schedules, output states, etc.) into Python data models. This mapping may use Pydantic models or dataclasses to define a structured representation of a device's state.

3. **Configuration Management:**
   
   * **View & Modify Settings:** Users will be able to view all configuration parameters of a selected device (or group of devices) and modify them through any interface (CLI commands, API calls, or GUI forms). This includes network settings, relay configurations, schedules, MQTT setup, name/labels, and any available parameter the Shelly device exposes.
   
   * **Bulk Application of Changes:** Changes can be applied at multiple scopes: to individual devices, to a selection of multiple devices, to all devices of a certain model/type, to a defined group of devices, or even to **all discovered devices**. For example, an admin could change the MQTT server setting on **all Shelly Plug S** devices at once, or disable the LED indicator on **every device in the "Office Floor" group**. This bulk operation significantly reduces repetitive work.
   
   * **State-Aware Configuration:** The tool will support conditional configuration logic – for instance, only apply a setting if a device is currently in a particular state. A practical use-case might be scheduling a firmware update command to devices that are currently idle (not in use) or only toggling a relay if it's off. Administrators can specify conditions (based on the fetched state from the device) under which a config change or action should execute. The system will skip or delay actions for devices that don't meet the criteria, ensuring safe configuration (important in industrial settings to avoid disruptions).
   
   * **Versioned Backups & Rollback:** Every time configuration changes are applied, the previous settings can be saved (exported) to a **versioned backup file** (e.g., as YAML or JSON) before the change. The tool will maintain a history of config snapshots for each device (or group), timestamped and labeled with the change description. If a change needs to be reverted, an operator can choose a previous version and instruct the tool to **rollback** the configuration, restoring the device to that known state. This is critical in enterprise environments for change management and quick recovery from errors.

4. **Grouping:**
   
   * **Persistent Device Groups:** Users can create and name groups of devices (e.g., by location, by function, or custom criteria). For example, define a group "Floor 1 Lights" containing all Shelly relays controlling lights on floor 1, or a group "Outdoor Sensors" for all weather-exposed Shelly sensors. Groups make it easier to issue bulk commands or check status at a glance.
   
   * **Group Definitions in YAML:** Group membership and metadata will be stored in a **YAML configuration file** (for easy editing and viewing). The YAML will list group names and the devices (by some identifier, e.g., device ID or IP or name) that belong to each group. Using YAML ensures the groups can be easily version-controlled and manually edited if needed. On startup, the tool will load group definitions from this file, and it can also export updated group files if changes are made through the interfaces.
   
   * **Dynamic and Static Grouping:** The tool may support static groups (explicitly defined as above) and potentially dynamic groups (groups based on a query or criterion, e.g., "all devices of type X" or "all devices currently online"). Dynamic grouping could be a future enhancement, but the foundation will allow grouping logic to be extensible. For now, the focus is on user-defined static group lists.

5. **Interfaces:** The system provides multiple interfaces to accommodate different use cases:
   
   * **Command-Line Interface (CLI):** A robust CLI will be built using Python libraries like `click` or `typer` for ease of use. The CLI will support various commands and subcommands for all major actions (discover, list, show config, set config, group operations, etc.). It should allow **command chaining** and flags for specifying targets (e.g., `shellymgr set wifi_ssid="MySSID" --group "Floor 1 Lights"`). Tab-completion and an interactive shell mode (where an admin can enter a REPL-like environment to run multiple commands) would be ideal for user friendliness. The CLI output will be formatted clearly (possibly with tables for device lists, or YAML/JSON output for detailed info if requested).
   
   * **REST API:** All functionality will be exposed via a RESTful API, so other tools or scripts can programmatically interact with the system. We will use a web framework (FastAPI or Flask) to define endpoints for each feature: e.g. `GET /devices` for discovered device list, `POST /devices/{id}/config` to apply settings, `GET /groups` to fetch group definitions, etc. The API will initially allow open access (for ease of use in a secure internal network) but will be designed such that adding authentication (API keys, JWT, or OAuth2) later is straightforward. By building with a framework like **FastAPI**, we also get interactive API docs (Swagger UI) out-of-the-box, which is helpful for development and integration.
   
   * **Web GUI:** A web-based Graphical Interface will be provided for users who prefer a dashboard. This will likely be a **React** front-end application that communicates with the Python backend (via the REST API). The GUI will be designed to be lightweight and responsive, suitable for desktop or tablet use. Key features of the GUI include: a dashboard of all discovered devices (with status indicators), pages to view and edit device configurations, group management screens, and possibly a log viewer. We will incorporate **internationalization (i18n)** support (using libraries such as `react-i18next`) so the UI text can be translated for non-English users. The frontend will be packaged to serve via the Python backend (e.g., as static files served by FastAPI/Flask) or hosted separately if needed, but a single Docker deployment will make it seamless.

6. **Polling and State Listening:**
   
   * **Periodic Polling:** The tool can optionally poll devices at configured intervals to get their latest status (e.g., power usage, online/offline state, sensor readings). Polling frequency can be global or per-group/per-device. This ensures the tool has up-to-date information even if devices don't push their state. The polling mechanism will be asynchronous (so many devices can be polled in parallel without blocking) and careful to avoid flooding the network (perhaps staggering polls or using adaptive intervals if the device count is high).
   
   * **Event Listening (Optional):** Many Shelly devices can push state updates via multicast (CoAP) or unicast (MQTT or HTTP callbacks). While full real-time event handling is not the initial focus, the architecture will not preclude it. For example, the tool might open a UDP socket to listen for CoAP broadcasts from Shelly Gen1 devices (which send state changes to the same 224.0.1.187:5683 multicast address​
     [github.com](https://github.com/StyraHem/ShellyForHASS/blob/master/troubleshooting.md#:~:text=The%20plugin%20trying%20to%20discover,mDns%20messages%20on%20the%20network)
     ). Additionally, Shelly Gen2 devices can be configured to send **MQTT** messages or use **WebSockets** for events; in the future the tool could incorporate an MQTT client or WebSocket server to subscribe to such updates. This would enable near-instant updates in the GUI when a device state changes (as opposed to waiting for the next poll). For now, implementing a **basic listener** for known Shelly multicast events will be considered (with an option to enable/disable it, since it might require network infrastructure support like IGMP).

7. **Data Storage:**
   
   * **Human-Readable Config Storage:** The system will use **YAML files** to store persistent data such as device metadata, saved configurations, and group definitions. YAML is chosen for its readability and ease of editing. For example, when devices are discovered, their basic info (ID, IP, type, etc.) might be saved to a `devices.yaml` for record-keeping. When configurations are backed up or groups are created, those are written to YAML files as well. This allows administrators to easily review or manually tweak these files if necessary.
   
   * **SQLite/JSON for Performance (Optional):** While YAML works great for human-friendly configs, it may become less efficient if there are thousands of devices or frequent writes (since parsing and writing YAML repeatedly can be slow). The tool's design will allow swapping in a lightweight database (like SQLite) or JSON files for certain data to improve performance. For instance, an **SQLite** database could be used as a cache for device states and logs, while still periodically dumping snapshots to YAML for transparency. The abstraction between the data layer and the logic will make this possible – e.g., using a repository pattern or data access layer that can switch between YAML or SQLite. By default, however, the simpler YAML approach will be used until scaling needs demand an upgrade.

8. **Logging and Monitoring:**
   
   * **Structured Logging:** A centralized logging subsystem will record all significant events and errors in the tool. This includes device discovery events (device found/lost), configuration changes (who/what changed), warnings (failed attempts, timeouts), and general info (startup, shutdown, background tasks, etc.). Logs will be in a structured format (e.g., JSON lines or key-value pairs) to facilitate filtering and analysis. Using Python's `logging` library, we can set up multiple handlers: console output, log file, and even an optional remote log collector (like sending logs to syslog or an ELK stack) if needed. Log levels will be configurable (DEBUG for verbose output during troubleshooting, INFO for normal operation, ERROR for issues, etc.). In enterprise usage, this level of logging is crucial for audit trails and diagnosing problems.
   
   * **Accessible via CLI/API/GUI:** The tool will provide ways to view recent logs through each interface. For example, a CLI command `shellymgr logs --tail 100` might show the last 100 log lines. The REST API might have an endpoint `/logs` that returns logs (with parameters for filtering by level or component). The Web GUI could have a "Logs" page or overlay where an administrator can see what's happening in real time (for instance, display new discovery events or errors). By exposing logs, users won't need to dig into container consoles or files for common monitoring tasks. Additionally, integration with external monitoring systems could be set up by forwarding these logs or triggering webhooks on certain events (e.g., send an alert if a device goes offline for >5 minutes).

9. **Internationalization (i18n):**
   
   * **Multi-Language Support:** From the start, the tool will be built with internationalization in mind. All user-facing strings in the CLI and GUI will be separable for translation. The CLI might support a flag to choose language for its messages, or more practically, it will ensure any messages (especially error descriptions or help texts) are easily translatable by maintaining them in a resource file. The Web GUI will definitely support multiple languages using a library like **react-i18next** (which allows loading language JSON files and switching languages on the fly).
   
   * **Unicode and Locales:** The system will fully support Unicode, so device names, group names, etc., can be in any language. Dates, times, and numbers will respect locale formatting in the GUI. While initial release might just include English, the framework will allow adding other languages. This is important for enterprise deployments in non-English-speaking regions. Documentation and README can also be translated accordingly to accompany the tool.

10. **Docker Deployment:**
    
    * **Containerization:** The entire application will be shipped with a **Dockerfile** to run it in a container. This ensures consistency across environments and makes it easy to deploy on a server or edge device without worrying about Python environment setup. The Docker image will contain the Python backend and can also serve the compiled frontend. For example, the container might run a Uvicorn server hosting the FastAPI app (which serves API and GUI), and we could invoke the CLI inside the container as needed (for one-off commands or debugging).
    
    * **Docker Compose Setup:** A `docker-compose.yml` will be provided to orchestrate the stack, especially if we decide to split components. For instance, we might have one service for the API backend and another for a dedicated frontend (or a reverse proxy like Nginx). However, a simpler approach is to keep it a single container for now. The compose file can also define volumes for persistent storage (so that YAML files or database storing device info and configs are persisted outside of the container). This makes upgrades easier – you can deploy a new container version while retaining your data. In an enterprise scenario, Docker deployment means the tool can be integrated into Kubernetes or other container management platforms as well, aligning with modern infrastructure practices.

Suggested Technologies and Frameworks
-------------------------------------

To implement the above features, we will utilize a stack of proven technologies in Python and JavaScript:

* **Backend (Python 3.11+):** Use **FastAPI** (preferred) or Flask for the REST API and for serving the web UI. FastAPI is ideal due to its asynchronous support and data validation via Pydantic models. Networking tasks (discovery, polling) will utilize `asyncio` for concurrency. For mDNS discovery, the `python-zeroconf` library can be used to listen for `_shelly._tcp.local` services and retrieve their info. For low-level network tasks or active scanning, libraries like `scapy` (for custom packets) or Python's `socket` can be used (for sending SSDP queries or handling raw UDP). HTTP interactions with devices can use **aiohttp** or Python's `requests` (though aiohttp fits the async model better). If CoAP support is needed, consider using `aiocoap` or similar. Data modeling will be helped by **Pydantic** (for defining device config schemas, used by FastAPI) or dataclasses.

* **Frontend (React):** A single-page application built with **React** will form the web GUI. We will use modern React (with hooks or possibly Next.js if server-side rendering needed, but likely overkill) along with a UI component library like **Chakra UI** or **Tailwind CSS** for a clean, responsive design. For state management, lightweight solutions like React Context or Redux Toolkit can manage device lists and configurations fetched from the API. For internationalization, **react-i18next** provides an easy way to manage multiple languages. The frontend will be built and packaged (using Webpack or Vite), producing static assets that the Python backend can serve.

* **CLI:** The CLI will be implemented in Python using either **Click** or **Typer**. Typer is built on Click and uses Python type hints, making it straightforward to define commands and options. It can auto-generate help messages and has support for nested subcommands (which is useful to mirror the feature set structure, e.g., `shellymgr devices list`, `shellymgr devices config get`, `shellymgr groups create`, etc.). Both Click and Typer support colorized output and shell completion which we will enable for better UX.

* **Storage:** Configuration and metadata will primarily use **PyYAML** to read/write YAML files. The YAML files will store device info, groups, and saved configurations in a structured manner. If performance becomes an issue or for concurrent access safety, we might use **SQLite** (via SQLAlchemy or Python's built-in `sqlite3`) as a small database. Another option for certain cached data is to use JSON files (since Python can easily read/write JSON and it's structured). However, YAML is preferred for its comments and readability. The architecture will isolate the storage mechanism so we can switch or combine these as needed (for example, using YAML for long-term config storage but SQLite for quick lookups and state caching).

* **Testing:** We will write unit and integration tests using **pytest**. Pytest's fixtures and parametrization will help test discovery (perhaps by simulating mDNS packets), configuration application (using a dummy Shelly device emulator or a mocked HTTP server), and CLI commands. We will aim for high code coverage. Additionally, we can use tools like `pytest-asyncio` to test async components. For the REST API, **FastAPI's** built-in test client or **HTTPX** can simulate API calls in tests. Continuous integration can be set up (e.g., GitHub Actions) to run tests and maybe build the Docker image on new commits.

* **Packaging & Deployment:** We'll provide a **Dockerfile** to containerize the application. This might be a multi-stage Docker build (one stage to build the React app, another to bundle it with the Python app). The final image will likely be based on a slim Python base (e.g., `python:3.11-slim`). For development convenience, a **docker-compose.yml** will let you run the API (and maybe a separate static file server or just the API itself) and possibly a watchdog for live reload during development. If needed, packaging to PyPI (as a Python package) can also be done so that advanced users can `pip install shelly-manager` and run it directly on a machine (though Docker is the recommended deployment).

Suggested Folder Structure
--------------------------

The project will be organized in a clear modular structure, separating concerns like discovery, configuration management, and interfaces. A possible directory layout is as follows:

text

CopyEdit

`shelly_manager/├── src/│   ├── discovery/           # Device scanning & mDNS/SSDP/CoAP discovery utilities│   ├── config_manager/      # Logic for reading, writing, and applying device settings│   ├── grouping/            # Group definitions & YAML handling for groups│   ├── state/               # Polling routines, conditional (state-aware) config logic│   ├── interfaces/│   │   ├── cli/             # CLI commands implementation (using click/typer)│   │   ├── api/             # REST API endpoints (FastAPI/Flask routes)│   │   └── web/             # React frontend source (or a built static folder)│   ├── utils/               # Utility modules (logging setup, network helpers, etc.)│   └── models/              # Data models (Pydantic models or dataclasses for device info, configs)├── config/                  # YAML templates, default config files (e.g., sample groups.yaml)├── tests/                   # Test cases for all modules├── docker/│   ├── Dockerfile           # Dockerfile for building the container image│   └── docker-compose.yml   # Docker Compose for development/production setup├── requirements.txt         # Python dependencies└── README.md                # Project documentation and usage instructions`

In this structure:

* The **discovery** module handles network scanning and discovery protocols.

* **config_manager** knows how to read from a device (get settings) and apply new settings (via HTTP/RPC calls).

* **grouping** manages loading/saving groups from YAML and provides functions to get devices by group.

* **state** could contain code for polling device status on intervals and evaluating conditional rules (like "only update if state X").

* **interfaces** contains subdirectories for each interface: the CLI commands, the API routes (which call into config_manager, grouping, etc.), and the web frontend (which might be a separate project but stored here for cohesion).

* **utils** might have logging configuration, helper functions (e.g., IP range generation, MDNS parsing code if not using a library), and perhaps wrapper classes for CoAP or other protocols.

* **models** define the shapes of data we handle – e.g., a Device model with fields like id, ip, type, firmware, config settings, etc., and possibly group model, config backup model, etc. Using Pydantic here would enforce correct types and allow easy serialization (to JSON/YAML).

This layout encourages separation of concerns and makes the codebase easier to navigate. For instance, adding a new feature in device discovery means touching the `src/discovery` module, and maybe extending the API and CLI to expose it, but other parts (like config_manager) remain unaffected.
Optional Future Enhancements
----------------------------

While the initial version focuses on the fundamentals, the design will keep the door open for advanced features. Some potential future improvements include:

* **Authentication & Security:** Add authentication mechanisms to the REST API (e.g., JWT token auth or OAuth2 flows) and user management for the GUI. In an enterprise setting, one might integrate with SSO/LDAP for the web interface. Also, securing the communication between frontend and backend (HTTPS, etc.) when deployed.

* **Scheduled Actions:** Allow users to schedule configuration changes or device actions at specific times. For example, schedule a reboot of certain devices at 3 AM, or apply a config change over the weekend. This scheduling could be handled by an internal scheduler (like APScheduler) or by integration with cron/Kubernetes CronJob when deployed.

* **MQTT and WebSocket Integration:** As mentioned, deeper integration with Shelly's real-time communication methods. For devices that support **MQTT**, the tool could act as an MQTT client, subscribing to topics for device status and even sending commands via MQTT. Similarly, for newer Shelly Pro/Plus devices that use a WebSocket (or HTTP long-poll) for status updates, the tool could maintain a live connection to get instantaneous updates. This would complement or replace the polling mechanism for better efficiency.

* **Rule Engine or Automation:** Build a layer on top for simple automations or conditional actions. For instance, "if sensor X temperature > 30°C, then turn off Shelly Plug Y" – a simple rules engine that could be configured via YAML or GUI. This steps slightly into home automation territory, but could be useful for standalone deployments.

* **Role-Based Access Control (RBAC):** In a multi-user environment, introduce roles/permissions. For example, a "viewer" role that can only read device status, an "operator" role that can execute certain pre-approved actions, and an "admin" role with full access. This would require a user system (hence authentication first) and then UI/API adjustments to enforce permissions on actions.

* **Scalability Enhancements:** If the number of devices grows very large (hundreds or thousands), further optimizations might be needed – such as sharding the discovery across multiple threads or processes, using a message queue (like Redis or MQTT) to handle device events, or even splitting the tool into microservices. Container orchestration (K8s) could then manage these components. The architecture we choose now (with clear module boundaries and using async where possible) will help in scaling out if needed.

* **Cloud/Remote Access:** Although designed for local network use, we could allow an option to connect via Shelly Cloud API or a remote access mode, so that devices across sites could be managed from a central instance. This is more complex and involves the Shelly Cloud API and careful security, but is a possible extension for enterprise scenarios with multiple locations.

By addressing the core features now and considering these future needs, this tool will provide immediate value in managing Shelly devices at scale, while laying the groundwork for a fully-fledged enterprise IoT device management solution. With a solid foundation in Python and a modular design, new capabilities can be added over time as the user requirements grow.

Overall, this specification aims to guide the development of a **robust, user-friendly, and extensible Shelly Device Management tool** that can be used from small installations up to large enterprise networks, ensuring efficient control over a fleet of Shelly smart devices.

## References (Appendix)

1. Shelly mDNS Discovery: https://shelly-api-docs.shelly.cloud/gen1/#shelly-family-overview_mdns
2. Shelly API Documentation: https://shelly-api-docs.shelly.cloud/
3. python-zeroconf: https://pypi.org/project/zeroconf/
4. FastAPI documentation: https://fastapi.tiangolo.com/
5. react-i18next for multilingual UIs: https://react.i18nextjs.com/
6. Typer CLI framework: https://typer.tiangolo.com/
7. MQTT with Shelly: https://shelly-api-docs.shelly.cloud/gen1/#mqtt
8. CoAP Discovery in Shelly: https://shelly-api-docs.shelly.cloud/gen1/#coap-discovery
9. Docker Compose: https://docs.docker.com/compose/
10. Shelly Plus/Pro Gen2 Devices RPC API: https://shelly-api-docs.shelly.cloud/gen2/
