const toggleSidebar = document.getElementById("toggleSidebar");
const sidebar = document.getElementById("sidebar");

if (toggleSidebar && sidebar) {
    toggleSidebar.addEventListener("click", () => {
        sidebar.classList.toggle("collapsed");
    });
}