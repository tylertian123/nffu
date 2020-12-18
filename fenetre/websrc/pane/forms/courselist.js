import React from 'react';
import {Alert, Button, ListGroup, Spinner} from 'react-bootstrap';
import {BsCheck, BsCheckAll, BsExclamationCircle} from 'react-icons/bs';
import {LinkContainer} from 'react-router-bootstrap';

import "regenerator-runtime/runtime";

function AdmCourseListEntry(props) {
	const course = props.course;
	let confstr = null;
	let editstr = null;

	if (course.configuration_locked) {
		confstr = <p className="text-success">Configuration verified <BsCheckAll /></p>;
		editstr = "Edit configuration";
	}
	else if (course.form_config || !course.has_attendance_form) {
		confstr = <p className="text-warning">Awaiting verification <BsCheck /></p>;
		editstr = "Review configuration";
	}
	else if (course.form_url) {
		confstr = <p className="text-warning">Waiting for configuration <BsExclamationCircle /></p>;
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
				{course.has_attendance_form && !course.form_config && course.form_url && (<li>
					<i>has unconfigured form URL</i>
				</li>)}
			</ul>
			<div className="align-self-end">
				{course.form_config_id && <LinkContainer to={"/forms/form/" + course.form_config_id}>
					<Button className="mx-1">Edit form</Button>
				</LinkContainer>}
				<LinkContainer to={"/forms/course/" + course.id}>
					<Button variant={course.configuration_locked ? "secondary" : "primary"}>{editstr}</Button>
				</LinkContainer>
			</div>
		</div>
	</ListGroup.Item>
}

function AdmCourseList() {
	const [courses, setCourses] = React.useState(null);

	React.useEffect(() => {
		(async () => {
			const response = await fetch("/api/v1/course");
			const data = await response.json();

			if (!response.ok) alert(data.error);
			else setCourses(data.courses);
		})()}, []);

	if (courses === null) {
		return <Alert className="d-flex align-items-center" variant="secondary"><Spinner className="mr-2" animation="border" /> loading...</Alert>;
	}
	else {
		return <>
			<ListGroup className="bg-light">
				{courses.map((x) => <AdmCourseListEntry key={x.id} course={x} />)}
			</ListGroup>
		</>;
	}
}

export default AdmCourseList;
