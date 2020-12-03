import React from 'react';

const UserInfoContext = React.createContext();
const AdminStateContext = React.createContext();

function UserInfoProvider(props) {
	return <UserInfoContext.Provider value={window.userinfo}>
		{props.children}
	</UserInfoContext.Provider>;
}

function AdminOnly(props) {
	const userinfo = React.useContext(UserInfoContext);
	if (userinfo.admin) return props.children;
	else return null;
}

export { UserInfoProvider, UserInfoContext, AdminOnly };
