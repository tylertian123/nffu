import reactModal from '@prezly/react-promise-modal';
import React from 'react';
import {Alert, Button, Col, Form, ListGroup, Modal, Row, Spinner} from 'react-bootstrap';
import {BsArrowLeft, BsPlay} from 'react-icons/bs';
import {LinkContainer} from 'react-router-bootstrap';
import {Link, Redirect, useParams} from 'react-router-dom';
import "regenerator-runtime/runtime";

import {FormFillStatusInner, IndividualError} from '../lockbox/status';
import useBackoffEffect from '../../common/pendprovider';

function IndividualTest(props) {
	const test = props.test;

	let headingstr = 'in-progress';
	if (test.is_finished) {
		headingstr = test.fill_result.result;
	}
	else {
		if (!test.in_progress) {
			headingstr = 'pending';
		}
	}

	return <ListGroup.Item>
		<div className="d-flex w-100 justify-content-between">
			<h4><code>{headingstr}</code> at {new Date(test.time_executed).toLocaleString('en-CA')}</h4>
			<Link className="alert-link" to={`test/${test.id}`}>view results</Link>
		</div>
		<ul>
			{test.is_finished && <li>finished at {new Date(test.fill_result.time_logged).toLocaleString('en-CA')}</li>}
			<li>encountered {test.errors.length} errors</li>
		</ul>
	</ListGroup.Item>;
}

function CourseTester() {
	const { idx } = useParams();

	const [ {course, tests}, setCourse ] = React.useState({course: null, tests: null});
	const [ error, setError ] = React.useState('');
	const [ starting, setStarting ] = React.useState(false);
	const [ newTest, setNewTest ] = React.useState(null);

	React.useEffect(() => {
		(async () => {
			const resp = await fetch("/api/v1/course/" + idx);
			const data = await resp.json();
			const resp2 = await fetch("/api/v1/course/" + idx + "/test");
			const data2 = await resp2.json();

			if (!resp.ok || !resp2.ok) {
				setError(data.error || data2.error);
				return;
			}

			setCourse({course: data.course, tests: data2.tests});
		})();
	}, [idx]);

	if (newTest !== null) {
		return <Redirect to={`/forms/course/${course.id}/test/${newTest}`} />;
	}

	if (course === null || tests == null) {
		if (error) {
			return <Alert variant="danger">failed: {error}</Alert>;
		}
		else {
			return <Alert className="d-flex align-items-center" variant="secondary"><Spinner className="mr-2" animation="border" /> loading...</Alert>;
		}
	}

	const startNewTest = async () => {
		setStarting(true);

		const resp = await fetch("/api/v1/course/" + idx + "/test", {
			"method": "POST"
		});

		const data = await resp.json();

		if (!resp.ok) {
			alert(data.error);
		}

		setNewTest(data.test.id);
	};

	return <div>
		<Link to={`/forms/course/${course.id}`}><span className="text-secondary"><BsArrowLeft /> Back</span></Link>

		<h1>Tests for {course.course_code}</h1>

		<Button onClick={startNewTest} disabled={starting} className="mb-2" variant="success"><BsPlay /> Run new test</Button>

		{tests.length > 0 && <ListGroup className="bg-light">
			{tests.map((x) => <IndividualTest key={x.id} test={x} />)}
		</ListGroup>}
		{tests.length > 0 || <Alert variant="info">No tests have been performed yet</Alert>}
	</div>;
}

function CourseTestViewer() {
	const { idx, testidx } = useParams();

	const [ course, setCourse ] = React.useState(null);
	const [ test, setTest ] = React.useState(null);
	const [ error, setError ] = React.useState('');
	const [ deleting, setDeleting ] = React.useState(false);

	React.useEffect(() => {
		(async () => {
			const resp = await fetch("/api/v1/course/" + idx);
			const data = await resp.json();

			if (!resp.ok) {
				setError(data.error);
				return;
			}

			setCourse(data.course);
		})();
	}, [idx]);

	useBackoffEffect(async () => {
		const resp = await fetch("/api/v1/course/" + idx + "/test/" + testidx);
		const data = await resp.json();

		if (!resp.ok) {
			setError(data.error);
			return false;
		}

		setTest(data.test);
		return !data.test.is_finished;
	}, []);

	if (course === null || test === null) {
		if (error) {
			return <Alert variant="danger">failed: {error}</Alert>;
		}
		else {
			return <Alert className="d-flex align-items-center" variant="secondary"><Spinner className="mr-2" animation="border" /> loading...</Alert>;
		}
	}
	
	return <div>
		<Link to={`/forms/course/${course.id}/test`}><span className="text-secondary"><BsArrowLeft /> Back</span></Link>
		<h1>Test results for {course.course_code}</h1>
		{test.in_progress && <Alert className="d-flex align-items-center" variant="success"><Spinner className="mr-2" animation="border" /> in progress...</Alert>}
		{!test.in_progress && !test.is_finished && <Alert className="d-flex align-items-center" variant="success"><Spinner className="mr-2" animation="border" /> pending...</Alert>}
		<ul>
			{test.is_finished && <li><i>finished</i></li>}

			<li>started at {new Date(test.time_executed).toLocaleString('en-CA')}</li>
			{test.is_finished && <li>finished at {new Date(test.fill_result.time_logged).toLocaleString('en-CA')}</li>}
			<li>encountered {test.errors.length} errors</li>
		</ul>
		<h1>Simulated status page</h1>
		<h2>Form filling status</h2>
		{test.fill_result ? <FormFillStatusInner status={{
			status: test.fill_result.result,
			related_course: test.fill_result.course,
			last_filled_at: test.fill_result.time_logged
		}} onlyOne baseUrl={`/api/v1/course/${idx}/test/${testidx}`} /> : <p>waiting</p>}
		<h2>Logged errors</h2>
		{test.errors.length > 0 ? <ListGroup className="bg-light">
			{test.errors.map((x) => <IndividualError key={x.id} errorData={x} />)}
		</ListGroup> : <Alert variant="info">No errors found!</Alert>}
	</div>;
}

export {CourseTester, CourseTestViewer};
