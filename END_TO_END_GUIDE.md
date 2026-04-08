# End-to-End Guide

## Complete Workflow

Your system now has a complete end-to-end workflow for face recognition attendance:

### 1. **Add Users** (User Management Page)
   - Navigate to "Users" in the menu
   - Click "Add User"
   - Fill in user details:
     - **User ID** (required) - Unique number for each user
     - **Name** (required)
     - Department, Contact, Address, etc.
   - Click "Save User"

### 2. **Capture Training Images** (Training Page)
   - Navigate to "Training" in the menu
   - Select a user from the dropdown
   - Click "Start Camera"
   - Click "Capture Image" multiple times (20-50 images recommended)
   - Try different angles, lighting, and expressions
   - The system will show how many images you've captured

### 3. **Train the Model** (Train Model Page)
   - Navigate to "Train Model" in the menu
   - Review the checklist
   - Click "Train Model"
   - Wait for training to complete
   - You'll see results showing:
     - Total images used
     - Number of unique users
     - Model save location

### 4. **Test Recognition** (Attendance Page)
   - Navigate to "Attendance" (home page)
   - Click "Start Camera"
   - Click "Capture & Recognize"
   - The system will:
     - Recognize the face (max 20 seconds)
     - Mark attendance automatically
     - Show user details and timestamp

## Quick Start

1. **Build the frontend:**
   ```bash
   cd frontend
   npm run build
   cd ..
   ```

2. **Start the server:**
   ```bash
   python app.py
   ```

3. **Open in browser:**
   - Go to: http://localhost:5000
   - You'll see navigation with 4 pages:
     - **Attendance** - Test face recognition
     - **Users** - Manage users
     - **Training** - Capture training images
     - **Train Model** - Train the recognition model

## Workflow Order

1. ✅ Add users first (User Management)
2. ✅ Capture training images (Training)
3. ✅ Train the model (Train Model)
4. ✅ Test recognition (Attendance)

## Tips

- **Training Images:** Capture 20-50 images per user for best accuracy
- **Lighting:** Use good lighting when capturing training images
- **Angles:** Capture from different angles (front, slight left, slight right)
- **Expressions:** Include different facial expressions
- **Testing:** After training, test with the same person to verify recognition

## API Endpoints

### User Management
- `GET /api/vendors` - List all users
- `POST /api/vendors` - Add new user
- `PUT /api/vendors/<id>` - Update user
- `DELETE /api/vendors/<id>` - Delete user

### Training
- `POST /api/training/capture` - Capture training image
- `GET /api/training/count/<user_id>` - Get image count
- `POST /api/training/train` - Train model
- `DELETE /api/training/delete/<user_id>` - Delete user images

### Attendance
- `POST /api/recognize` - Recognize face and mark attendance
- `GET /api/attendance` - Get attendance records
- `GET /api/status` - System status

## Troubleshooting

### "No face detected"
- Ensure good lighting
- Face should be clearly visible
- Try adjusting camera angle

### "User not found in database"
- Make sure you've added the user first
- Check that the User ID matches

### "No training images found"
- Capture training images before training
- Check that images are in the `data/` folder

### Recognition not working
- Train the model after capturing images
- Ensure you've captured enough images (20+)
- Try retraining with more images

## File Structure

```
data/
  user.1.1.jpg  # Training images (user ID, image number)
  user.1.2.jpg
  user.2.1.jpg
  ...

classifier.xml  # Trained model (created after training)
```

## Next Steps

1. Add your first user
2. Capture training images
3. Train the model
4. Test recognition
5. Add more users and repeat!

The system is now fully functional end-to-end! 🎉


