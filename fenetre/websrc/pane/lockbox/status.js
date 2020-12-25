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
import {imageHighlight} from '../../common/confirms';

import "regenerator-runtime/runtime";

function FormFillStatus() {
	const [status, setStatus] = React.useState(null);
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
				setStatus(data)
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
	switch (status.status) {
		case "no-form":
			return <Alert variant="info">We haven't yet filled in any forms for you!</Alert>;
		case "success":
			el = <Alert variant="success">Your last form was filled succesfully!</Alert>;
			break;
		case "failure":
			el = <Alert variant="danger">Oh no! Your last form didn't fill in properly. You probably need to do it manually.</Alert>;
			break;
		case "failure":
			el = <Alert variant="warning">Oh no! Your last form <i>may not have</i> filled in properly. You might need to do it manually.</Alert>;
			break;
	}

	return <div>
		{el}
		<ul>
			<li>Last filled in at: {new Date(status.last_filled_at).toLocaleString('en-CA')}</li>
		</ul>
		<h2>Screenshots</h2>
		<Row>
			<Col lg className="mb-2">
				<img onClick={() => imageHighlight("/api/v1/me/lockbox/form_status/form_thumb.png")} 
					className="d-block img-fluid img-thumbnail" src="/api/v1/me/lockbox/form_status/form_thumb.png" />
			</Col>
			<Col lg className="mb-2">
				<img onClick={() => imageHighlight("/api/v1/me/lockbox/form_status/confirm_thumb.png")} 
					className="d-block img-fluid img-thumbnail" src="/api/v1/me/lockbox/form_status/confirm_thumb.png" />
			</Col>
		</Row>
	</div>
}

function ErrorList() {
	return null;
}

function Status() {
	return <div>
		<h1>Form filling status</h1>
		<FormFillStatus />
		<h2>Logged errors</h2>
		<ErrorList />
	</div>;
}

export default Status;
