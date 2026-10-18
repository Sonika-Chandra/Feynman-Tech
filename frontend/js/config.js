// Where the backend lives. When the page is opened from the backend (http://localhost:5000/) this is automatic.
const API = location.protocol === "file:" ? "http://localhost:5000" : location.origin;
