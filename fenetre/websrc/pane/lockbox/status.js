import React from 'react';
import {Alert, Button, Col, ListGroup, Row, Spinner} from 'react-bootstrap';
import {Link} from 'react-router-dom';
import {imageHighlight} from '../../common/confirms';
import {ExtraUserInfoContext} from '../../common/userinfo';

import "regenerator-runtime/runtime";

function FormFillStatus() {
	const [status, setStatus] = React.useState(null);
	const [relatedCourse, setRelatedCourse] = React.useState(null);
	const [ error, setError ] = React.useState('');

	React.useEffect(() => {
		(async () => {
			const resp = await fetch("/api/v1/me/lockbox/form_status");
			const data = await resp.json();

			if (!resp.ok) {
				setError(data.error);
				return;
			}
			else {
				if (data.related_course) {
					const course_info = await fetch(`/api/v1/course/${data.related_course}`);
					const cdata = await course_info.json()

					if (course_info.ok) {
						setRelatedCourse(cdata.course);
					}
					setStatus(data);
				}
				else {
					setStatus(data)
				}
			}
		})();
	}, []);

	if (status === null) {
		if (error) {
			return <Alert variant="danger">failed: {error}</Alert>;
		}
		else {
			return <Alert className="d-flex align-items-center" variant="secondary"><Spinner className="mr-2" animation="border" /> loading...</Alert>;
		}
	}

	let el = null;
	let show_screenshots = [false, false];

	switch (status.status) {
		case "no-form":
			return <Alert variant="info">We haven't yet filled in any forms for you!</Alert>;
		case "success":
			el = <Alert variant="success">Your last form was filled succesfully!</Alert>;
			show_screenshots = [true, true];
			break;
		case "submit-disabled":
			el = <Alert variant="success">NFFU is currently in test mode and so we're not submitting forms, but your form was filled in succesfully.</Alert>;
			show_screenshots = [true, true];
			break;
		case "failure":
			el = <Alert variant="danger">Oh no! Your last form didn't fill in properly. You probably need to do it manually.</Alert>;
			break;
		case "possible-failure":
			el = <Alert variant="warning">Oh no! Your last form <i>may not have</i> filled in properly. You might need to do it manually.</Alert>;
			show_screenshots = [true, false];
			break;
		default:
			el = <Alert variant="warning">Unknown status</Alert>;
			break;
	}

	return <div>
		{el}
		<ul>
			{relatedCourse !== null && <li>Filled in for <code>{relatedCourse.course_code}</code>. <Link className="alert-link" to={`/lockbox/cfg/${relatedCourse.id}`}>View configuration</Link></li>}
			<li>Last filled in at: {new Date(status.last_filled_at).toLocaleString('en-CA')}</li>
		</ul>
		{show_screenshots.some((x) => x) && <>
			<h2>Screenshots</h2>
			<Row>
				{show_screenshots[0] && 
				<Col lg className="mb-2">
					<img onClick={() => imageHighlight("/api/v1/me/lockbox/form_status/form_thumb.png")} 
						className="d-block img-fluid img-thumbnail" src="/api/v1/me/lockbox/form_status/form_thumb.png" />
				</Col>}
				{show_screenshots[1] && 
					<Col lg className="mb-2">
						<img onClick={() => imageHighlight("/api/v1/me/lockbox/form_status/confirm_thumb.png")} 
							className="d-block img-fluid img-thumbnail" src="/api/v1/me/lockbox/form_status/confirm_thumb.png" />
					</Col>}
			</Row>
		</>}
	</div>
}

function IndividualError(props) {
	const errorData = props.errorData;
	const [isGone, setGone] = React.useState(false);
	const [isDeleting, setDeleting] = React.useState(false);

	const doDelete = async() => {
		setDeleting(true);
		try {
			const resp = await fetch(`/api/v1/me/lockbox/errors/${errorData.id}`, {
				method: "DELETE"
			});

			if (resp.ok) {
				setGone(true);
			}
			else {
				alert((await resp.json()).error);
			}
		}
		finally {
			setDeleting(false);
		}
	};

	if (isGone) {
		return <ListGroup.Item><i>cleared</i></ListGroup.Item>;
	}

	return <ListGroup.Item>
		<div className="d-flex w-100 justify-content-between">
			<h4><code>{errorData.kind}</code></h4>
			<p>at {new Date(errorData.time_logged).toLocaleString('en-CA')}</p>
		</div>
		<div className="d-flex justify-content-md-between w-100 flex-wrap flex-md-nowrap">
			<p className="w-100">{errorData.message}</p>
			<Button onClick={doDelete} disabled={isDeleting} className="mt-1">{isDeleting ? <Spinner size="sm" animation="border" /> : 'Clear'}</Button>
		</div>
	</ListGroup.Item>
}

function ErrorList() {
	const [errors, setErrors] = React.useState(null);
	const [error, setError] = React.useState('');

	React.useEffect(() => {
		(async () => {
			const resp = await fetch("/api/v1/me/lockbox/errors");
			const data = await resp.json();

			if (!resp.ok) {
				setError(data.error);
				return;
			}
			else {
				setErrors(data.lockbox_errors)
			}
		})();
	}, []);

	if (errors === null) {
		if (error) {
			return <Alert variant="danger">failed: {error}</Alert>;
		}
		else {
			return <Alert className="d-flex align-items-center" variant="secondary"><Spinner className="mr-2" animation="border" /> loading...</Alert>;
		}
	}

	if (errors.length == 0) {
		return <Alert variant="info">No errors found!</Alert>;
	}

	return <ListGroup className="bg-light">
		{errors.map((x) => <IndividualError key={x.id} errorData={x} />)}
	</ListGroup>;
}

function Status() {
	const eui = React.useContext(ExtraUserInfoContext);

	if (eui === null) return <Alert className="d-flex align-items-center" variant="secondary"><Spinner className="mr-2" animation="border" /> loading...</Alert>;
	if (!eui.lockbox_credentials_present) {
		return <Alert variant="danger">You haven't set your TDSB credentials yet!</Alert>;
	}

	return <div>
		{eui.lockbox_form_active || <Alert variant="info">You've currently turned off form filling, so we won't fill any more forms for you until you turn it back on <Link className="alert-link" to="/lockbox/cfg">here</Link></Alert>}
		<h1>Form filling status</h1>
		<FormFillStatus />
		<h2>Logged errors</h2>
		<ErrorList />
	</div>;
}

export default Status;
