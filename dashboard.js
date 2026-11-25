async function loadDashboard() {
  try {
    const response = await fetch("/api/tasks");
    if (!response.ok) throw new Error("Could not load tasks.");
    const data = await response.json();
    const tasks = data.tasks;
    const completed = tasks.filter(task => task.completed).length;
    const pending = tasks.length - completed;
    document.querySelector("#total-count").textContent = tasks.length;
    document.querySelector("#pending-count").textContent = pending;
    document.querySelector("#completed-count").textContent = completed;
    const rate = tasks.length ? Math.round(completed / tasks.length * 100) : 0;
    document.querySelector("#completion-rate").textContent = rate;
    document.querySelector("#progress-fill").style.width = rate + "%";
    const list = document.querySelector("#recent-task-list");
    list.replaceChildren();
    tasks.slice(-5).reverse().forEach(task => {
      const row = document.createElement("div");
      row.className = "recent-task";
      row.innerHTML = `<i class="task-dot${task.completed ? " completed" : ""}"></i><strong></strong><small>${task.completed ? "Completed" : "In progress"}</small>`;
      row.querySelector("strong").textContent = task.task;
      list.append(row);
    });
  } catch (error) {
    console.error(error);
  }
}
document.querySelector("#today-label").textContent = new Intl.DateTimeFormat(undefined,{weekday:"short",month:"short",day:"numeric"}).format(new Date());
loadDashboard();
