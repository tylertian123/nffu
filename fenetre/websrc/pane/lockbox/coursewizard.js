import React from 'react';
import {Alert, Button, Col, Form, FormCheck, Row, Spinner} from 'react-bootstrap';
import {BsArrowLeft, BsCheck} from 'react-icons/bs';
import {Link, Redirect, useParams} from 'react-router-dom';
import "regenerator-runtime/runtime";
import {imageHighlight} from '../../common/confirms';
import useBackoffEffect from '../../common/pendprovider';

const InnerCourseContext = React.createContext();

function QuestionHeader(props) {
	return <h2 className={props.completed ? "text-success" : ""}>{props.children}{' '}{props.completed && <BsCheck className="text-success" />}</h2>
}

function FormPresentQuestion(props) {
	return <>
		<QuestionHeader completed={props.completed}>Does this course use an attendance form?</QuestionHeader>
		<p>Only answer "no" if you never need to fill in an asynchronous attendance form for this course (e.g. it's a placeholder for co-op or similar)</p>
		<hr />
		<div className="w-100 d-flex justify-content-end">
			<Button disabled={props.completed} onClick={() => props.onFill(true)} variant="success" className="mx-2">Yes</Button> <Button disabled={props.completed} onClick={() => props.onFill(false)} variant="danger" className="mx-2">No</Button>
		</div>
	</>;
}

function ConfirmGeneric(props) {
	return <>
		<QuestionHeader completed={false}>Confirm configuration:</QuestionHeader>
		<p>{props.children}</p>
		<hr />
		<div className="w-100 d-flex justify-content-between">
			<Button disabled={props.completed} onClick={props.onBack} variant="secondary"><BsArrowLeft /> Back</Button>
			<Button disabled={props.completed} onClick={props.onComplete} variant="success" className="mx-2">Yes</Button>
		</div>
	</>;
}

function FormUrlQuestion(props) {
	const FORM_REGEX = /^(?:https?:\/\/)?docs.google.com\/forms(?:\/u\/\d+)?\/d\/e\/([A-Za-z0-9-_]+)\/viewform/;

	const current = props.value;
	let error = null;
	if (!current) {
		error = "the url is required";
	}
	else {
		if (!FORM_REGEX.test(current)) {
			error = "that doesn't look like a google form url";
		}
	}

	const verifyAndSend = () => {
		if (!FORM_REGEX.test(current)) return;
		const match = current.match(FORM_REGEX);
		const formid = match[1];
		props.onChange(`https://docs.google.com/forms/d/e/${formid}/viewform`);
		props.onFill();
	};

	return <>
		<QuestionHeader completed={props.completed}>What is the URL of your attendance form?</QuestionHeader>
		<p>This should be a link to a Google Form. It should contain the word <code>viewform</code> in it somewhere.</p>
		<Form.Group>
			<Form.Control disabled={props.completed} isInvalid={!!error} value={current} onChange={(e) => props.onChange(e.target.value)} placeholder="Enter the URL here" type="text" />
			<Form.Control.Feedback type="invalid">{error}</Form.Control.Feedback>
		</Form.Group>
		<hr />
		<div className="w-100 d-flex justify-content-between">
			<Button disabled={props.completed} onClick={props.onBack} variant="secondary"><BsArrowLeft /> Back</Button>
			<Button disabled={props.completed} onClick={verifyAndSend} variant="success" className="mx-2">OK</Button>
		</div>
	</>;
}

function ChooseFormConfigQuestion(props) {
	const course = React.useContext(InnerCourseContext);

	const [options, setOptions] = React.useState(null);

	const formUrl = props.formUrl;

	useBackoffEffect(async () => {
		const resp = await fetch("/api/v1/course/" + course.id + "/config_options", {
			method: "POST",
			headers: {"Content-Type": "application/json"},
			body: JSON.stringify({"form_url": formUrl})
		});
		const data = await resp.json();
		if (!resp.ok) {
			alert("failed to grab");
		}
		else {
			if (data.status == "pending") return true;
			const options = data.options;
			if (options.length == 0) {
				props.onNoOptions();
			}
			else {
				setOptions(options);
			}
		}
		return false;
	}, [formUrl, course.id]);

	const verifyAndSend = () => {
		if (props.value === null) return;
		props.onFill();
	}

	if (options === null) {
		return <Alert className="d-flex align-items-center" variant="secondary"><Spinner className="mr-2" animation="border" /> Processing form...</Alert>;
	}

	return <>
		<QuestionHeader completed={props.completed}>Which of these form styles best matches your form?</QuestionHeader>
		<p>If none of them are correct, choose "none of the above" and an administrator will be able to create a new one from the URL you've provided.</p>
		{options.map((option) => <Form.Check key={option.token} type="radio" custom id={"upd-option-" + option.token}>
			<Form.Check.Input type="radio" type="radio" disabled={props.completed} onChange={(e) => {if (e.target.checked) props.onChange(option.token)}} checked={props.value == option.token} />
			<Form.Check.Label className="w-100">
				<Row>
					<Col md={option.has_thumbnail ? "7" : null}>
						<p><b>{option.form_title}</b> <br />
						<small>option provided due to: <code>{option.reason}</code></small></p>
					</Col>
					{option.has_thumbnail &&
					<Col md>
						<img className="d-block img-fluid img-thumbnail" src={`/api/v1/course/${course.id}/config_options/${option.token}/thumb.png`} 
												onClick={() => imageHighlight(`/api/v1/course/${course.id}/config_options/${option.token}/thumb.png`)} />
					</Col>}
				</Row>
			</Form.Check.Label>
		</Form.Check>)}
		<FormCheck label="None of the above" type="radio" disabled={props.completed} onChange={(e)=>{if (e.target.checked) props.onChange('')}} custom id={"upd-option-def"} checked={props.value == ''} />
		<hr />
		<div className="w-100 d-flex justify-content-between">
			<Button disabled={props.completed} onClick={props.onBack} variant="secondary"><BsArrowLeft /> Back</Button>
			<Button disabled={props.completed} onClick={verifyAndSend} variant="success" className="mx-2">OK</Button>
		</div>
	</>
}

function CourseWizard() {
	const { idx } = useParams();

	const [ course, setCourse ] = React.useState(null);
	const [ error, setError ] = React.useState('');

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

	const [questionState, setQuestionState] = React.useState('ask-attendance');
	const [formUrl, setFormUrl] = React.useState('');
	const [chosenConfigStr, setChosenConfigStr] = React.useState(null);
	const [redirecting, setRedirecting] = React.useState(false);

	if (course === null) {
		if (error) {
			return <Alert variant="danger">failed: {error}</Alert>;
		}
		else {
			return <Alert className="d-flex align-items-center" variant="secondary"><Spinner className="mr-2" animation="border" /> loading...</Alert>;
		}
	}

	const PREV_STATES = {
		'confirm-no-attendance': 'ask-attendance',
		'ask-form-url': 'ask-attendance',
		'ask-config-profile': 'ask-form-url',
		'confirm-form': 'ask-config-profile',
		'confirm-nooption-form': 'ask-form-url'
	};

	const handleBack = () => {
		setQuestionState(PREV_STATES[questionState]);
	}

	const STATE_COMPONENT_MAP = {
		'ask-attendance': FormPresentQuestion,
		'confirm-no-attendance': ConfirmGeneric,
		'ask-form-url': FormUrlQuestion,
		'ask-config-profile': ChooseFormConfigQuestion,
		'confirm-form': ConfirmGeneric,
		'confirm-nooption-form': ConfirmGeneric
	}

	const sendConfiguration = async (payload) => {
		const resp = await fetch("/api/v1/course/" + idx + "/config", {
			method: "PUT",
			headers: {"Content-Type": "application/json"},
			body: JSON.stringify(payload)
		});

		if (resp.ok) {
			setRedirecting(true);
		}
		else {
			setError((await resp.json()).error);
		}
	};

	const STATE_PROPS = {
		'ask-attendance': {
			onFill: (value) => {
				if (value) {
					setQuestionState('ask-form-url');
				}
				else {
					setQuestionState('confirm-no-attendance');
				}
			}
		},
		'confirm-no-attendance': {
			onComplete: () => {
				sendConfiguration({
					has_form_url: false
				});
			},
			children: <p>The course <code>{course.course_code}</code> will be configured to not require asynchronous attendance form filling. Is this correct?</p>
		},
		'ask-form-url': {
			value: formUrl,
			onChange: setFormUrl,
			onFill: () => {
				setQuestionState('ask-config-profile');
			}
		},
		'ask-config-profile': {
			value: chosenConfigStr,
			onChange: setChosenConfigStr,
			formUrl: formUrl,
			onFill: () => {
				setQuestionState('confirm-form')
			},
			onNoOptions: () => {
				setQuestionState('confirm-nooption-form')
			}
		},
		'confirm-form': {
			onComplete: () => {
				sendConfiguration({
					has_form_url: true,
					form_url: formUrl,
					config_token: chosenConfigStr == '' ? undefined : chosenConfigStr
				})
			},
			children: chosenConfigStr == '' ? <p>The course <code>{course.course_code}</code> will be configured with the above URL and an administrator will have to create a new style for it. Is this correct?</p> :
											  <p>The course <code>{course.course_code}</code> will be configured with the above URL and form style. Is this correct?</p>
		},
		'confirm-nooption-form': {
			onComplete: () => {
				sendConfiguration({
					has_form_url: true,
					form_url: formUrl
				})
			},
			children: <p>We couldn't find any styles that worked with that form, so the course <code>{course.course_code}</code> will be configured with the above URL and an administrator will have to create a new style for it. Is this correct?</p>
		}
	}

	let questions = [];
	let currstate = questionState;
	// Add the current question
	questions.push(React.createElement(STATE_COMPONENT_MAP[currstate], {completed: false, onBack: handleBack, ...STATE_PROPS[currstate]}));
	while (currstate in PREV_STATES) {
		currstate = PREV_STATES[currstate];
		questions.splice(0, 0, React.createElement(STATE_COMPONENT_MAP[currstate], {completed: true, onBack: handleBack, ...STATE_PROPS[currstate]}));
	}

	return <div>
		<Link to={"/lockbox/cfg/"+idx}><span className="text-secondary"><BsArrowLeft /> Cancel</span></Link>
		<h1>Configuring <b>{course.course_code}</b></h1>
		<Alert variant="warning">Please be aware that the changes you make here affect all users in this course, not just you.</Alert>
		<InnerCourseContext.Provider value={course}>
			{questions.map((x) => <><hr />{x}</>)}
		</InnerCourseContext.Provider>
		{redirecting && <Redirect to={"/lockbox/cfg/"+idx} />}
	</div>;
}

export default CourseWizard;
