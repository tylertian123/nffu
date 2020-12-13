import React from 'react';

import {Row, Col, FormCheck, Form, Button, Alert, Spinner, ListGroup} from 'react-bootstrap';
import {ExtraUserInfoContext} from '../../common/userinfo';
import {useFormik} from 'formik';
import * as yup from 'yup';
import {Link, Redirect, Switch, Route, useParams} from 'react-router-dom';
import useBackoffEffect from '../../common/pendprovider';
import CourseWizard from './coursewizard';

import {BsCheckAll, BsCheck, BsExclamationCircle, BsArrowRight, BsArrowLeft, BsArrowClockwise} from 'react-icons/bs';

import "regenerator-runtime/runtime";

function CredentialChangerAlerts() {
	const eui = React.useContext(ExtraUserInfoContext);
	if (eui === null) return null;

	return eui.lockbox_credentials_present ? 
		<Alert variant="success">You've already filled in your TDSB credentials; you only need to use this area if you changed your password.</Alert> :
		<Alert variant="warning">You haven't filled out your TDSB credentials yet; to start filling in forms you need to set them here.</Alert>;
}

function CredentialChanger() {
	const schema = yup.object({
		username: yup.string().required().matches(/\d{5,9}/, "username should be 5 to 9 digits"),
		password: yup.string().required()
	});

	const eui = React.useContext(ExtraUserInfoContext);

	const [done, setDone] = React.useState(false);

	const doSubmit = async (values, {setStatus, setFieldError}) => {
		if (done) setDone(false);

		try {
			const response = await fetch('/api/v1/me/lockbox', {
				method: "PATCH",
				headers: {"Content-Type": "application/json"},
				body: JSON.stringify({
					username: values.username,
					password: values.password
				})
			});
			if (!response.ok) {
				const data = await response.json();

				if (data.error == "invalid request" && "extra" in data) {
					if ("username" in data.extra) setFieldError("username", data.extra["username"]);
					if ("password" in data.extra) setFieldError("password", data.extra["password"]);
				}
				else {
					setStatus(data.error);
				}
			}
			else {
				setDone(true);
				eui.invalidate();
			}
		}
		catch (err) {
			setStatus(err);
		}
	};

	const formik = useFormik({
		initialValues: {username: '', password: ''},
		onSubmit: doSubmit,
		validationSchema: schema
	});

	return <>
		<CredentialChangerAlerts />
		<Form noValidate onSubmit={formik.handleSubmit}>
			{done && <p className="text-success">Saved!</p>}
			{formik.status && <p className="text-danger">{formik.status}</p>}
			<Form.Group>
				<Form.Label>TDSB Username</Form.Label>
				<Form.Control type="text" name="username" isInvalid={!!formik.errors.username && formik.touched.username} {...formik.getFieldProps('username')} />
				<Form.Control.Feedback type="invalid">{formik.errors.username}</Form.Control.Feedback>
			</Form.Group>

			<Form.Group>
				<Form.Label>TDSB Password</Form.Label>
				<Form.Control type="password" name="password" isInvalid={!!formik.errors.password && formik.touched.password} {...formik.getFieldProps('password')} />
				<Form.Control.Feedback type="invalid">{formik.errors.password}</Form.Control.Feedback>
			</Form.Group>

			<Button type="submit" disabled={formik.isSubmitting || eui === null}>{formik.isSubmitting ? (<Spinner className="mb-1" animation="border" size="sm" variant="light" />) : "Update credentials"}</Button>
		</Form>
	</>;
};

function Enabler() {
	const [working, setWorking] = React.useState(false);
	const eui = React.useContext(ExtraUserInfoContext);
	const [privateEnabled, setPrivateEnabled] = React.useState(eui.lockbox_form_active);
	const [status, setStatus] = React.useState('');

	const update = async (e) => {
		const oldValue = privateEnabled;
		const nv = e.target.checked;

		setPrivateEnabled(nv);
		setWorking(true);

		try {
			const response = await fetch('/api/v1/me/lockbox', {
				method: "PATCH",
				headers: {"Content-Type": "application/json"},
				body: JSON.stringify({
					active: nv
				})
			});

			if (!response.ok) {
				const data = await response.json();
				setPrivateEnabled(oldValue);
				setStatus(data.error);
			}
		}
		catch (err) {
			setStatus(err);
		}
		finally {
			setWorking(false);
		}
	};

	return <>
		{status && <p className="text-danger">{status}</p>}
		<FormCheck onChange={update} checked={privateEnabled} disabled={working || eui === null} custom id="form-enable" type="switch" label="Enable form-filling" />
		{working && <Spinner size="sm" animation="border" />}
	</>;
};

function CourseDetector() {
	const [courses, setCourses] = React.useState(null);
	const [pending, setPending] = React.useState(null);

	const reloadCourses = useBackoffEffect(async () => {
		const response = await fetch("/api/v1/me/lockbox/courses");
		const data = await response.json();
		const pending = data.status == "pending";

		setPending(pending);

		if (pending) return true;
		setCourses(data.courses);
		return false;
	}, []);

	const refreshCourses = async () => {
		const resp = await fetch('/api/v1/me/lockbox/courses/update', {method: "POST"});
		if (!resp.ok) return;
		setCourses(null);
		reloadCourses();
	};

	if (courses === null) {
		if (pending !== null && pending) {
			return <Alert className="d-flex align-items-center" variant="info"><Spinner className="mr-2" animation="border" /> We're still grabbing your courses from TDSB Connects; please wait a bit.</Alert>;
		}
		else {
			return <Alert className="d-flex align-items-center" variant="secondary"><Spinner className="mr-2" animation="border" /> loading...</Alert>;
		}
	}
	else {
		let alertstr = null;

		if (courses !== null) {
			if (courses.every((x) => !x.configuration_locked && (x.form_config || !x.has_attendance_form))) {
				alertstr = <Alert variant="warning">All of your courses have valid configurations, however some of them have not been verified yet. You might want to check them (and possibly amend them) yourself.</Alert>;
			}
			else if (courses.some((x) => !x.configuration_locked)) {
				alertstr = <Alert variant="danger">Oh no! Some of your courses haven't been configured yet! Please try configuring them yourself <i>before</i> asking an administrator to.</Alert>;
			}
			else {
				alertstr = <Alert variant="info">Good news! We have configurations for all of your courses!</Alert>;
			}
		}
		
		return <>
			{alertstr}
			<ListGroup className="bg-light">
				{courses.map((x) => <CourseListEntry key={x.id} course={x} />)}
			</ListGroup>
			<Button className="mt-3" onClick={refreshCourses}><BsArrowClockwise /> Refresh from TDSB Connects</Button>
		</>;
	}
}

function CourseListEntry(props) {
	const course = props.course;
	let confstr = null;
	let editstr = null;

	const [redirecting, setRedirecting] = React.useState(false);

	if (course.configuration_locked) {
		confstr = <p className="text-success">Configuration verified <BsCheckAll /></p>;
		editstr = "View configuration";
	}
	else if (course.form_config || !course.has_attendance_form) {
		confstr = <p className="text-warning">Configured by other user <BsCheck /></p>;
		editstr = "Review configuration";
	}
	else if (course.form_url) {
		confstr = <p className="text-warning">Waiting for administrator to configure <BsExclamationCircle /></p>;
		editstr = "Review submitted information";
	}
	else {
		confstr = <p className="text-danger">Not configured <BsExclamationCircle /></p>;
		editstr = "Configure";
	}

	return <ListGroup.Item>
		<div className="text-dark d-flex w-100 justify-content-between">
			<h3 className="mb-1">{course.course_code}</h3>
			{confstr}
		</div>
		<div className="d-flex w-100 justify-content-between">
			<ul>
				{course.teacher_name && <li>Taught by <span className="text-info">{course.teacher_name}</span></li>}
				{course.known_slots.length > 0 && <li>In slots <span className="text-info">{course.known_slots.join(", ")}</span></li>}
				{!course.has_attendance_form && <li>No form required</li>}
				{!course.form_config && course.form_url && (<li>
					<i>awaiting form style setup from administrator</i>
				</li>)}
			</ul>
			<Button className="align-self-end" onClick={() => setRedirecting(true)} variant={course.configuration_locked ? "secondary" : "primary"}>{editstr} <BsArrowRight /></Button>
			{redirecting && <Redirect to={"/lockbox/cfg/" + course.id} />}
		</div>
	</ListGroup.Item>
}

function CfgMain() {
	const eui = React.useContext(ExtraUserInfoContext);

	if (eui !== null && !eui.has_lockbox_integration) return null;

	return (<div>
		<Row>
			<Col sm className="mb-3">
				<h2>Change credentials</h2>
				<CredentialChanger />
			</Col>
			<Col sm>
				<h2>Form-filling configuration</h2>
				{eui !== null &&
					<Enabler />}
			</Col>
		</Row>
		{eui !== null && eui.lockbox_credentials_present && (<Row>
			<Col>
				<h2>Detected courses</h2>
				<CourseDetector />
			</Col>
		</Row>)}
	</div>);
};

function CourseViewer() {
	const { idx } = useParams();

	const [ course, setCourse ] = React.useState(null);
	const [ error, setError ] = React.useState('');

	const [redirecting, setRedirecting] = React.useState(false);

	React.useEffect(() => {
		(async () => {
			const resp = await fetch("/api/v1/course/" + idx);
			const data = await resp.json();

			if (!resp.ok) {
				setError(data.error);
				return;
			}
			
			if (data.course.form_config) {
				const resp2 = await fetch("/api/v1/course/" + idx + "/form");
				const data2 = await resp2.json();

				if (!resp2.ok) {
					setError(data2.error);
					return;
				}
				setCourse({
					...data.course,
					form_config_data: data2.form
				});
			}
			else {
				setCourse(data.course);
			}
		})();
	}, [idx]);

	if (course === null) {
		if (error) {
			return <Alert variant="danger">failed: {error}</Alert>;
		}
		else {
			return <Alert className="d-flex align-items-center" variant="secondary"><Spinner className="mr-2" animation="border" /> loading...</Alert>;
		}
	}

	let current_config = null;

	if (!course.has_attendance_form) {
		current_config = <Alert variant="secondary">Course set as not having an attendance form to fill in.</Alert>;
	}
	else if (course.form_url) {
		current_config = <Row>
			<Col lg="6">
				<ul>
					{course.form_config_data && (<>
						<li>Form style: <code>{course.form_config_data.name}</code></li>
					</>)}
					<li>URL: <a href={course.form_url}><code>{course.form_url}</code></a></li>
					{!course.form_config_data && (<li>
						<i>awaiting form style setup from administrator</i>
					</li>)}
				</ul>
			</Col>
			{course.form_config_data && (<Col lg>
				{course.form_config_data.has_thumbnail ? 
					<img className="d-block img-fluid img-thumbnail" src={`/api/v1/course/${course.id}/form/thumb.png`} />
				:   <p>no thumbnail available</p>}
			</Col>)}
		</Row>
	}

	let reconfig = null;

	if (course.configuration_locked) {
		reconfig = <p class="text-muted"><BsCheckAll /> This course was verified by an admin, so you can't edit its configuration. If you think it's wrong, tell an admin directly.</p>;
	}
	else {
		reconfig = current_config === null ? <Button onClick={() => setRedirecting(true)} variant="success">Start configuring <BsArrowRight /></Button> :
			<Button onClick={() => setRedirecting(true)}>Reconfigure <BsArrowClockwise /></Button>;
	}

	return <div>
		<Link to="/lockbox/cfg"><span className="text-secondary"><BsArrowLeft /> Back</span></Link>

		<h1>{course.course_code}</h1>

		<ul>
			{course.teacher_name && <li>Taught by <span className="text-info">{course.teacher_name}</span></li>}
			{course.known_slots.length > 0 && <li>In slots <span className="text-info">{course.known_slots.join(", ")}</span></li>}
		</ul>

		<hr />

		{current_config && (<>
			<h2>Current configuration</h2>
			{current_config}
		</>)}
		
		<div className="w-100 d-flex justify-content-end mt-2">{reconfig}</div>

		{redirecting && <Redirect to={"/lockbox/cfg/" + course.id + "/setup"} />}
	</div>
}

function Cfg() {
	return <Switch>
		<Route path="/lockbox/cfg" exact>
			<CfgMain />
		</Route>
		<Route path="/lockbox/cfg/:idx/setup">
			<CourseWizard />
		</Route>
		<Route path="/lockbox/cfg/:idx">
			<CourseViewer />
		</Route>
	</Switch>;
}

export default Cfg;
