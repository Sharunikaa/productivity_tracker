from flask import Flask, render_template, request, redirect, url_for, session, flash
import networkx as nx
import matplotlib.pyplot as plt
from datetime import datetime
import time
import threading
import io
import base64

app = Flask(__name__)
app.secret_key = 'your_secret_key'

class ProjectTracker:
    def __init__(self):
        self.tasks = {}
        self.attendance = {}
        self.completed_tasks = set()
        self.task_actual_times = {}
        self.G = nx.DiGraph()
        self.productivity_report = {}  

    def get_project_details(self, project_name, tasks_data):
        self.project_name = project_name
        for task_no, task_info in tasks_data.items():
            task_name = task_info['name']
            duration = task_info['duration']
            dependencies = task_info['dependencies']
            self.tasks[task_no] = {
                'name': task_name,
                'duration': duration,
                'dependencies': dependencies
            }

    def create_task_graph(self):
        self.G.clear()
        for task_no, task_info in self.tasks.items():
            self.G.add_node(task_no, name=task_info['name'], duration=task_info['duration'])
            for dependency in task_info['dependencies']:
                self.G.add_edge(dependency, task_no, weight=task_info['duration'])

    def draw_graph(self):
        pos = nx.spring_layout(self.G)
        node_colors = ['red' if node in self.completed_tasks else 'lightblue' for node in self.G.nodes()]

        nx.draw_networkx_nodes(self.G, pos, node_size=700, node_color=node_colors)
        nx.draw_networkx_edges(self.G, pos, edgelist=self.G.edges(data=True), width=2)
        labels = {node: f"{data['name']}\n({data['duration']})" for node, data in self.G.nodes(data=True)}
        nx.draw_networkx_labels(self.G, pos, labels, font_size=12)
        edge_labels = {(u, v): f"{d['weight']}" for u, v, d in self.G.edges(data=True)}
        nx.draw_networkx_edge_labels(self.G, pos, edge_labels=edge_labels)

        plt.title("Project Task Dependency Graph")
        img = io.BytesIO()
        plt.savefig(img, format='png')
        img.seek(0)
        graph_url = base64.b64encode(img.getvalue()).decode('utf8')
        plt.close()
        return graph_url

    def topological_sort(self):
        try:
            topo_sort = list(nx.topological_sort(self.G))
            return topo_sort
        except nx.NetworkXUnfeasible:
            return []

    def critical_path_analysis(self):
        try:
            path = nx.dag_longest_path(self.G, weight='duration')
            length = sum(self.G.nodes[task]['duration'] for task in path)
            return path, length
        except nx.NetworkXUnfeasible:
            return [], 0

    def shortest_path(self, start, end):
        try:
            length, path = nx.single_source_dijkstra(self.G, source=start, target=end, weight='duration')
            return path, length
        except nx.NetworkXNoPath:
            return [], 0

    def track_time_and_notify(self, task_no):
        task = self.tasks[task_no]
        duration = task['duration']
        print(f"Task {task_no} ({task['name']}) started for {duration} minutes.")
        start_time = datetime.now()
        time.sleep(duration * 60)
        end_time = datetime.now()
        actual_duration = (end_time - start_time).total_seconds() / 60
        self.task_actual_times[task_no] = actual_duration

        print(f"Time is up for task {task_no} ({task['name']}).")
        completed = input(f"Is task {task_no} completed? (yes/no): ").strip().lower()
        if completed == "yes":
            self.completed_tasks.add(task_no)
            actual_duration = int(input("Enter actual duration in minutes: "))
            self.mark_task_completed(task_no, actual_duration)
        else:
            delay = int(input("How many minutes of delay? "))
            self.tasks[task_no]['duration'] += delay
            self.create_task_graph()
            self.critical_path_analysis()
    
    def update_productivity(self, task_no, actual_duration):
        planned_duration = self.tasks[task_no]['duration']
        productivity = (actual_duration / planned_duration) * 100 if planned_duration > 0 else 0
        self.productivity_report[task_no] = productivity

    def mark_task_completed(self, task_no, actual_duration):
        self.completed_tasks.add(task_no)
        self.task_actual_times[task_no] = actual_duration
        planned_duration = self.tasks[task_no]['duration']
        productivity = (actual_duration / planned_duration) * 100 if planned_duration > 0 else 0
        self.productivity_report[task_no] = productivity
        self.generate_productivity_report()

    def manage_attendance_and_leave(self, employee_name, action):
        today = datetime.today().date()
        if employee_name not in self.attendance:            
            self.attendance[employee_name] = {'present': set(), 'leave': set()}
        if action == 'present':
            self.attendance[employee_name]['present'].add(today)
        elif action == 'leave':
            self.attendance[employee_name]['leave'].add(today)

    def generate_productivity_report(self):
        report = []
        total_planned_time = sum(task['duration'] for task in self.tasks.values())
        total_actual_time = sum(self.task_actual_times.get(task_no, 0) for task_no in self.tasks)

        for task_no, task_info in self.tasks.items():
            planned_time = task_info['duration']
            actual_time = self.task_actual_times.get(task_no, 0)
            productivity = (actual_time / planned_time) * 100 if planned_time > 0 else 0
            report.append({
                'task_no': task_no,
                'task_name': task_info['name'],
                'planned_time': planned_time,
                'actual_time': actual_time,
                'productivity': productivity
            })

        overall_productivity = (total_actual_time / total_planned_time) * 100 if total_planned_time > 0 else 0
        self.productivity_report = report 
        self.overall_productivity = overall_productivity  
        return report, overall_productivity


project_tracker = ProjectTracker()

@app.route('/')
def home():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    session['username'] = username
    flash(f'Logged in as {username}')
    return redirect(url_for('project_input'))

@app.route('/project_input', methods=['GET', 'POST'])
def project_input():
    if request.method  == 'POST':
        project_name = request.form['project_name']
        num_tasks = int(request.form['num_tasks'])
        tasks_data = {}
        for i in range(1, num_tasks + 1):
            task_name = request.form[f'task_name_{i}']
            duration = int(request.form[f'duration_{i}'])
            dependencies = request.form[f'dependencies_{i}'].split(',')
            dependencies = [int(dep) for dep in dependencies if dep]
            tasks_data[i] = {'name': task_name, 'duration': duration, 'dependencies': dependencies}
        project_tracker.get_project_details(project_name, tasks_data)
        project_tracker.create_task_graph()
        return redirect(url_for('graph'))
    return render_template('project_input.html')

@app.route('/graph', methods=['GET', 'POST'])
def graph():
    if request.method == 'POST':
        if 'task_completed' in request.form:
            task_no = int(request.form['task_completed'])
            actual_duration = int(request.form['actual_duration'])
            project_tracker.mark_task_completed(task_no, actual_duration)
            flash(f'Task {task_no} marked as completed.')
            return redirect(url_for('graph'))
    graph_url = project_tracker.draw_graph()
    topo_sort = project_tracker.topological_sort()
    path, length = project_tracker.critical_path_analysis()
    productivity_report, overall_productivity = project_tracker.generate_productivity_report()
    return render_template('graph.html', graph_url=graph_url, topo_sort=topo_sort, critical_path=path,
                           critical_path_length=length, productivity_report=productivity_report,
                           overall_productivity=overall_productivity)

@app.route('/topological_sort')
def topological_sort():
    topo_sort = project_tracker.topological_sort()
    return render_template('topological_sort.html', topo_sort=topo_sort)

@app.route('/critical_path')
def critical_path():
    path, length = project_tracker.critical_path_analysis()
    return render_template('critical_path.html', critical_path=path, critical_path_length=length)

@app.route('/shortest_path', methods=['GET', 'POST'])
def shortest_path():
    if request.method == 'POST':
        start = int(request.form['start'])
        end = int(request.form['end'])
        path, length = project_tracker.shortest_path(start, end)
        total_weight = sum(project_tracker.G.edges[path[i], path[i + 1]]['weight'] for i in range(len(path) - 1))
        path_names = [project_tracker.G.nodes[task]['name'] for task in path]
        return render_template('shortest_path.html', path=path_names, total_weight=total_weight)
    return render_template('shortest_path.html')

@app.route('/productivity_report')
def productivity_report():
    report, overall_productivity = project_tracker.generate_productivity_report()
    return render_template('productivity_report.html', report=report, overall_productivity=overall_productivity)

if __name__ == '__main__':
    app.run(debug=True)
