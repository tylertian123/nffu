import reactModal from '@prezly/react-promise-modal';
import React from 'react';
import {Alert, Button, Col, Form, ListGroup, Modal, Row, Spinner} from 'react-bootstrap';
import {BsArrowLeft, BsArrowRight} from 'react-icons/bs';
import {LinkContainer} from 'react-router-bootstrap';
import {Link, useParams} from 'react-router-dom';
import "regenerator-runtime/runtime";

import {imageHighlight} from '../../common/confirms';


function SelectFormInner(props) {
	const {onSubmit, onDismiss, show} = props;
	const [forms, setForms] = React.useState(null);

	React.useEffect(() => {
		(async () => {
			const resp = await fetch("/api/v1/form");
			if (!resp.ok) {
				alert((await resp.json()).error);
				setForms([]);
				return;
			}

			const data = await resp.json();
			setForms(data.forms);
		})();
	}, []);

	const [selectedForm, setSelectedForm] = React.useState(null);

	return <Modal centered show={show} onHide={onDismiss}>
		<Modal.Header>
			<Modal.Title>
				<h1>Select form style</h1>
			</Modal.Title>
		</Modal.Header>

		<Modal.Body>
			{forms === null ? <Alert className="d-flex align-items-center" variant="secondary"><Spinner className="mr-2" animation="border" /> loading...</Alert> :
			<ListGroup className="bg-light">
				{forms.map((x) => <ListGroup.Item key={x.id} active={selectedForm && x.id == selectedForm.id} action onClick={() => setSelectedForm(x)}>
					{x.name}
				</ListGroup.Item>)}
			</ListGroup>}
		</Modal.Body>

		<Modal.Footer>
			<Button variant="secondary" onClick={onDismiss}>Cancel</Button>
			<Button disabled={selectedForm === null} variant="primary" onClick={() => {onSubmit(selectedForm)}}>Select</Button>
		</Modal.Footer>
	</Modal>
}

function selectForm() {
	return reactModal(({show, onSubmit, onDismiss}) => {
		return <SelectFormInner show={show} onSubmit={onSubmit} onDismiss={onDismiss} />;
	});
}

function CourseConfigurator(props) {
	const [ isDirty, setIsDirty ] = React.useState(false);
	const [ isSaving, setIsSaving ] = React.useState(false);

	const [ {course, form}, dispatch ] = React.useReducer((state, action) => {
		const newstate = {...state};
		setIsDirty(true);
		switch (action.type) {
			case 'set_locked':
				newstate.course.configuration_locked = action.value;
				break;
			case 'set_has_form':
				newstate.course.has_attendance_form = action.value;
				break;
			case 'set_form_url':
				newstate.course.form_url = action.value;
				break;
			case 'set_form':
				newstate.course.form_config = true;
				newstate.course.form_config_id = action.value.id;
				newstate.form = action.value;
				break;
		}
		return newstate;
	}, {form: props.form, course: props.course});

	// TODO: add verification client-side here (it's already done server-side)
	const save = async () => {
		let payload = {
			configuration_locked: course.configuration_locked,
			has_attendance_form: course.has_attendance_form
		};

		if (payload.has_attendance_form) {
			payload.form_url = course.form_url;
			if (form && form.id) {
				payload.form_config_id = form.id;
			}
		}

		setIsSaving(true);

		const resp = await fetch("/api/v1/course/" + course.id, {
			method: "PATCH",
			headers: {"Content-Type": "application/json"},
			body: JSON.stringify(payload)
		});

		setIsSaving(false);

		if (!resp.ok) {
			alert((await resp.json()).error);
			return;
		}

		setIsSaving(false)
		setIsDirty(false);
		props.onChange({course: course, form: form});
	}

	return <div>
		<Row>
			<Col md="4">
				<Form.Check checked={course.configuration_locked} onChange={(e) => dispatch({type: 'set_locked', value: e.target.checked})}
					custom type="switch" label="Verified / locked" id="course-verified" />
				<Form.Check checked={course.has_attendance_form} onChange={(e) => dispatch({type: 'set_has_form', value: e.target.checked})}
					custom type="switch" label="Has attendance form" id="course-has-attendance" />
			</Col>
			<Col md="8">
				<Form.Group>
					<Form.Label>Form URL</Form.Label>
					<Form.Control type="text" value={course.form_url ? course.form_url : ''} disabled={!course.has_attendance_form}
						onChange={(e) => dispatch({type: "set_form_url", value: e.target.value})} />
				</Form.Group>
				<Form.Group>
					<Form.Label>Form style</Form.Label>
					{form &&
					<ListGroup className="bg-light border-0 rounded-bottom-0 mb-0">
						<ListGroup.Item className="border-0">
							<h3 className="text-dark d-inline mb-0">{form.name}</h3>
							<div className="d-flex mt-2 w-100 justify-content-between align-items-end">
								<ul className="mb-0">
									<li>Used by <span className="text-info">{form.used_by}</span> courses</li>
									{form.is_default && <li><i>is default</i></li>}
									{!!form.representative_thumbnail || <li><i>no thumbnail set</i></li>}
								</ul>
								<LinkContainer to={"/forms/form/" + form.id}>
									<Button>Edit <BsArrowRight /></Button>
								</LinkContainer>
							</div>
						</ListGroup.Item>
					</ListGroup>}
					<Button disabled={!course.has_attendance_form} className={form ? "rounded-top-0 w-100" : "w-100"}
						onClick={async () => {
							const choice = await selectForm();
							if (choice) {
								dispatch({type: "set_form", value: choice});
							}
						}}>
						{form ? "Change": "Add"}
					</Button>
				</Form.Group>
			</Col>
		</Row>
		<hr />
		<div className="d-flex w-100 justify-content-end">
			<Button onClick={save} disabled={!isDirty || isSaving}>{isSaving ? <Spinner size="sm" animation="border" /> : 'Save'}</Button>
		</div>
	</div>
}

function CourseEditor() {
	const { idx } = useParams();

	const [ {course, form}, setCourse ] = React.useState({form: null, course: null});
	const [ error, setError ] = React.useState('');

	React.useEffect(() => {
		(async () => {
			const resp = await fetch("/api/v1/course/" + idx);
			const data = await resp.json();

			if (!resp.ok) {
				setError(data.error);
				return;
			}

			if (data.course.form_config_id) {
				const resp2 = await fetch("/api/v1/form/" + data.course.form_config_id);
				const data2 = await resp2.json();

				if (!resp2.ok) {
					setError(data2.error);
					return;
				}
				setCourse({
					course: data.course,
					form: data2.form
				});
			}
			else {
				setCourse({course: data.course, form: null});
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
		current_config = <ul>
			<li><i>no form required</i></li>
		</ul>
	}
	else if (course.form_url) {
		current_config = <Row>
			<Col lg="6">
				<ul>
					{form && (<>
						<li>Form style: <code>{form.name}</code></li>
						<ul>
							<li>Used by <span className="text-info">{form.used_by - 1}</span> other courses</li>
							<li>Editable <Link className="alert-link" to={`/forms/form/${form.id}`}>here</Link></li>
						</ul>
					</>)}
					<li>URL: <a href={course.form_url}><code>{course.form_url}</code></a></li>
					{!course.form_config && (<li>
						<i>awaiting form style setup</i>
					</li>)}
					{form && <li>Test configuration <Link className="alert-link" to={`/forms/course/${course.id}/test`}>here</Link></li>}
				</ul>
			</Col>
			{form && (<Col lg>
				{!!form.representative_thumbnail ? 
					<img onClick={() => imageHighlight(`/api/v1/course/${course.id}/form/thumb.png`)} 
						className="d-block img-fluid img-thumbnail" src={`/api/v1/course/${course.id}/form/thumb.png`} />
						:   <p>no thumbnail available</p>}
			</Col>)}
		</Row>
	}

	return <div>
		<Link to="/forms/course"><span className="text-secondary"><BsArrowLeft /> Back</span></Link>

		<h1>{course.course_code}</h1>

		<ul>
			{course.teacher_name && <li>Taught by <span className="text-info">{course.teacher_name}</span></li>}
			{course.known_slots.length > 0 && <li>In slots <span className="text-info">{course.known_slots.join(", ")}</span></li>}
		</ul>

		<hr />

		{current_config && (<>
			<h2>Current configuration</h2>
			{current_config}
			<hr />
		</>)}

		<h2>Edit configuration</h2>

		<CourseConfigurator form={form} course={course} onChange={(v) => setCourse(v)} />
	</div>
}

export default CourseEditor;
