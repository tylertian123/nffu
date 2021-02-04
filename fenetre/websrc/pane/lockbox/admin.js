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
		<h1>Tasks</h1>
		<Button variant="success" onClick={onUpdateCourses}>Update all user courses</Button>
	</div>;
}

export default LockAdmin;
