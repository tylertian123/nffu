import React from 'react';

import {Row, Col, FormCheck, Form, Button, Alert, Spinner, ListGroup} from 'react-bootstrap';
import {LinkContainer} from 'react-router-bootstrap';
import {ExtraUserInfoContext} from '../../common/userinfo';
import {useFormik} from 'formik';
import * as yup from 'yup';
import {Link, Switch, Route, useParams} from 'react-router-dom';
import useBackoffEffect from '../../common/pendprovider';
import CourseWizard from './coursewizard';

import {BsCheckAll, BsCheck, BsExclamationCircle, BsArrowRight, BsArrowLeft, BsArrowClockwise} from 'react-icons/bs';
import {confirmationDialog} from '../../common/confirms';

import "regenerator-runtime/runtime";

function TaskEntry(props) {
	const task = props.task;

	return <ListGroup.Item>
		<div className="d-flex w-100 justify-content-between">
			<h4><code>{task.kind}</code></h4>
			<small>{task.owner}</small>
		</div>
		<ul>
			{task.is_running && <li>Currently running</li>}
			{task.retry_count > 0 && <li>Retried <span class="text-info">{task.retry_count}</span> times so far</li>}
			<li>scheduled for {new Date(task.next_run_at).toLocaleString('en-CA')}</li>
		</ul>
	</ListGroup.Item>
}

function TaskViewer() {
	const [version, setVersion] = React.useState(0);
	const [tasks, setTasks] = React.useState([]);
	const [pending, setPending] = React.useState(false);

	React.useEffect(async() => {
		if (version == 0) return;
		setPending(true);

		const resp = await fetch('/api/v1/admin/debug/tasks');
		const data = await resp.json();

		setTasks(data.tasks);
		setPending(false);
	}, [version]);

	return <div>
		<ListGroup className="bg-light">
			{tasks.map((x) => <TaskEntry task={x} />)}
		</ListGroup>
		<Button className="mt-3" onClick={() => setVersion(version + 1)} disabled={pending}>
			{pending ? <Spinner size="sm" animation="border" /> : null} {version == 0 ? " Load" : " Reload"}
		</Button>
	</div>
}

function LockAdmin() {
	const onUpdateCourses = async () => {
		if (!await confirmationDialog(<p>Are you <i>really</i> sure you want to schedule updating <i>all</i> user courses? You should really only be doing this between quads.</p>)) {
			return;
		}

		const resp = await fetch('/api/v1/admin/update_user_courses', {method: "POST"});
		if (!resp.ok) {
			alert("failed");
		}
	};

	return <div>
		<h1>Actions</h1>
		<Button variant="success" onClick={onUpdateCourses}>Update all user courses</Button>
		<h1>Debug</h1>
		<h2>Task View</h2>
		<TaskViewer />
	</div>;
}

export default LockAdmin;
